"""
BioPlan MCP server — same tools the FastAPI agent uses.
Run: PYTHONPATH=/var/CRM_test .venv/bin/python -m mcp_server
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
from backend.app.services.patch import apply_plan_patch_dict
from backend.app.services.plan_store import plan_to_dict, push_snapshot, _replace_plan_content
from backend.app.services.validate import validate_plan_dict

mcp = FastMCP("bioplan")


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


@mcp.tool()
def get_plan_snapshot() -> str:
    """Return current plan snapshot as JSON."""
    db, plan = _db_plan()
    try:
        return json.dumps(plan_to_dict(db, plan), ensure_ascii=False, indent=2)
    finally:
        db.close()


@mcp.tool()
def validate_plan() -> str:
    """Validate current plan invariants."""
    db, plan = _db_plan()
    try:
        errs = validate_plan_dict(plan_to_dict(db, plan))
        return json.dumps({"ok": not errs, "errors": errs}, ensure_ascii=False)
    finally:
        db.close()


@mcp.tool()
def apply_plan_patch(operations_json: str) -> str:
    """
    Apply batch patch. operations_json: JSON array of operations
    or object {"operations": [...]}.
    """
    db, plan = _db_plan()
    try:
        raw = json.loads(operations_json)
        ops = raw if isinstance(raw, list) else raw.get("operations") or []
        current = plan_to_dict(db, plan)
        new_plan, changes, errors = apply_plan_patch_dict(
            current, {"operations": ops}, changed_by="agent"
        )
        if errors:
            return json.dumps({"ok": False, "errors": errors, "changes": []}, ensure_ascii=False)
        push_snapshot(db, plan, source="agent")
        _replace_plan_content(db, plan, new_plan, changed_by="agent")
        db.commit()
        return json.dumps({"ok": True, "errors": [], "changes": changes}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return json.dumps({"ok": False, "errors": [str(exc)], "changes": []}, ensure_ascii=False)
    finally:
        db.close()


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
