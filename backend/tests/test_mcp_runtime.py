"""Shared MCP tool runtime: dry_run, undo, overloaded, batch limit."""

from backend.app.services.mcp_runtime import MAX_BATCH_OPS, execute_tool
from backend.app.services.plan_store import plan_to_dict, push_snapshot


def test_dry_run_does_not_mutate(db, mini_plan):
    _user, plan = mini_plan
    before = plan_to_dict(db, plan)
    ops = [{"op": "shift", "filter": {"phase_code": "P2"}, "days": 10}]
    result, changes = execute_tool(
        db, plan, "apply_plan_patch", {"operations": ops, "dry_run": True}
    )
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["changes"]
    assert changes == []
    db.commit()
    after = plan_to_dict(db, plan)
    assert after["tasks"][0]["start_date"] == before["tasks"][0]["start_date"]


def test_apply_over_hard_limit(db, mini_plan):
    _user, plan = mini_plan
    ops = [{"op": "shift", "filter": {"code": "T2.1"}, "days": 1}] * (MAX_BATCH_OPS + 1)
    result, changes = execute_tool(db, plan, "apply_plan_patch", {"operations": ops})
    assert result["need_clarification"] is True
    assert changes == []


def test_apply_large_create_wbs_schedules_cascade(db, mini_plan):
    _user, plan = mini_plan
    ops = [
        {
            "op": "create",
            "code": f"TX.{i}",
            "parent": "P2",
            "position": "end",
            "title": f"Leaf {i}",
            "duration_days": 3,
            "predecessors": [f"TX.{i-1}"] if i > 1 else ["T2.1"],
        }
        for i in range(1, 6)
    ]
    planned, _ = execute_tool(db, plan, "plan_commands", {"operations": ops})
    assert planned["ok"] is True
    result, changes = execute_tool(db, plan, "apply_plan_patch", {"operations": ops})
    assert result["ok"] is True
    assert len(changes) == 5
    db.commit()
    snap = plan_to_dict(db, plan)
    by = {t["code"]: t for t in snap["tasks"]}
    assert {"TX.1", "TX.5"} <= set(by)
    # Waterfall: each next leaf starts after previous ends (not one column)
    assert by["TX.2"]["start_date"] > by["TX.1"]["start_date"]
    assert by["TX.5"]["start_date"] > by["TX.4"]["start_date"]


def test_undo_plan_tool(db, mini_plan):
    _user, plan = mini_plan
    push_snapshot(db, plan, source="test")
    plan.title = "Mutated"
    db.flush()
    result, _ = execute_tool(db, plan, "undo_plan", {})
    assert result["ok"] is True
    db.commit()
    db.refresh(plan)
    assert plan.title == "Mini"


def test_list_overloaded_assignees(db, mini_plan):
    _user, plan = mini_plan
    result, changes = execute_tool(db, plan, "list_overloaded_assignees", {"top_n": 3})
    assert result["ok"] is True
    assert result["total_leaf_tasks"] >= 1
    assert isinstance(result["top"], list)
    assert changes == []


def test_mcp_server_surfaces():
    """Smoke: FastMCP registers tools, resource, prompt (no Cursor needed)."""
    from mcp_server import mcp

    tool_names = {t.name for t in mcp._tool_manager.list_tools()}
    assert "get_plan_snapshot" in tool_names
    assert "apply_plan_patch" in tool_names
    assert "undo_plan" in tool_names
    assert "list_overloaded_assignees" in tool_names

    resources = list(mcp._resource_manager.list_resources())
    uris = {str(r.uri) for r in resources}
    assert "plan://current" in uris

    prompts = list(mcp._prompt_manager.list_prompts())
    names = {p.name for p in prompts}
    assert "golden_shift_preclinical" in names
