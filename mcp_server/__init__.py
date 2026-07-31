"""
BioPlan MCP server — same tools the FastAPI agent uses (mcp_runtime).

Run from repo root:
  PYTHONPATH=. .venv/bin/python -m mcp_server

Cursor config: see README.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ensure repo root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from backend.app.database import SessionLocal, init_db
from backend.app.models import Plan, User
from backend.app.services.mcp_runtime import execute_tool

mcp = FastMCP(
    "bioplan",
    instructions=(
        "BioPlan MCP: read/validate/patch the R&D Gantt plan in SQLite. "
        "Web chat agent uses the same mcp_runtime in-process; this server is stdio for Cursor."
    ),
)


def _db_plan(plan_id: int | None = None) -> tuple:
    init_db()
    db = SessionLocal()
    if plan_id:
        plan = db.get(Plan, plan_id)
    else:
        login = os.environ.get("BIOPLAN_MCP_USER", "pm")
        user = db.scalars(select(User).where(User.login == login)).first()
        if not user:
            db.close()
            raise RuntimeError(f"User {login} not found — run make seed")
        plan = db.scalars(select(Plan).where(Plan.user_id == user.id)).first()
    if not plan:
        db.close()
        raise RuntimeError("Plan not found")
    return db, plan


def _run(name: str, args: dict | None = None) -> str:
    db, plan = _db_plan()
    try:
        result, _changes = execute_tool(db, plan, name, args or {})
        if isinstance(result, dict) and result.get("ok") and name == "apply_plan_patch":
            if not result.get("dry_run"):
                db.commit()
        elif isinstance(result, dict) and result.get("ok") and name == "undo_plan":
            db.commit()
        elif name in ("get_plan_snapshot", "validate_plan", "list_overloaded_assignees"):
            pass
        else:
            # failed mutate — rollback any flush
            if name in ("apply_plan_patch", "undo_plan"):
                db.rollback()
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False)
    finally:
        db.close()


@mcp.tool()
def get_plan_snapshot() -> str:
    """Return current plan snapshot as JSON."""
    return _run("get_plan_snapshot")


@mcp.tool()
def validate_plan() -> str:
    """Validate current plan invariants."""
    return _run("validate_plan")


@mcp.tool()
def apply_plan_patch(operations_json: str, dry_run: bool = False) -> str:
    """
    Apply plan patch (up to 60 operations). Pass the full WBS in one call.
    operations_json: JSON array or {"operations": [...]}. dry_run=true previews
    without writing. start_date is recomputed from predecessors after create/deps.
    """
    raw = json.loads(operations_json)
    ops = raw if isinstance(raw, list) else raw.get("operations") or []
    return _run("apply_plan_patch", {"operations": ops, "dry_run": dry_run})


@mcp.tool()
def undo_plan() -> str:
    """Undo last plan change (restore previous snapshot)."""
    return _run("undo_plan")


@mcp.tool()
def list_overloaded_assignees(top_n: int = 5) -> str:
    """Who is overloaded: top assignees by leaf task count (read-only)."""
    return _run("list_overloaded_assignees", {"top_n": top_n})


@mcp.resource("plan://current")
def plan_current() -> str:
    """Current plan snapshot (same as get_plan_snapshot)."""
    return _run("get_plan_snapshot")


@mcp.prompt()
def golden_shift_preclinical() -> str:
    """Golden demo prompt G1: shift preclinical phase."""
    return (
        "Сдвинь всю доклинику на 10 дней. "
        "Сначала get_plan_snapshot или resource plan://current, "
        "затем apply_plan_patch с одной shift-операцией "
        '(filter.phase_code для фазы доклиники / P2, days=10). '
        "При сомнении используй dry_run=true."
    )


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
