"""Agent tool contract: plan_commands / apply / limit / import errors."""

from backend.app.models import AgentJob
from backend.app.services.agent import MAX_BATCH_OPS, _run_tool
from backend.app.services.plan_store import plan_to_dict


def test_plan_commands_ok_stores_ops(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True}
    ops = [
        {"op": "shift", "filter": {"phase_code": "P2"}, "days": 5},
        {"op": "reassign", "filter": {"phase_code": "P2"}, "assignee": "Иванов"},
    ]
    result, changes = _run_tool(
        db, plan, "plan_commands", {"operations": ops, "analysis": "ok"}, ctx=ctx
    )
    assert result["ok"] is True
    assert result["need_clarification"] is False
    assert result["count"] == 2
    assert ctx["planned_ops"] == ops
    assert changes == []


def test_plan_commands_over_limit_clarifies(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True}
    ops = [
        {"op": "shift", "filter": {"code": "T2.1"}, "days": i} for i in range(MAX_BATCH_OPS + 1)
    ]
    result, changes = _run_tool(db, plan, "plan_commands", {"operations": ops}, ctx=ctx)
    assert result["ok"] is False
    assert result["need_clarification"] is True
    assert result["count"] == MAX_BATCH_OPS + 1
    assert ctx.get("planned_ops") is None
    assert changes == []


def test_apply_requires_plan_commands(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True, "planned_ops": None}
    ops = [{"op": "shift", "filter": {"phase_code": "P2"}, "days": 3}]
    result, changes = _run_tool(
        db, plan, "apply_plan_patch", {"operations": ops}, ctx=ctx
    )
    assert result["ok"] is False
    assert "plan_commands" in (result["errors"][0] if result.get("errors") else "")
    assert changes == []
    before = plan_to_dict(db, plan)
    assert before["tasks"][0]["start_date"] == "2026-07-01"


def test_apply_after_plan_commands_mutates(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True}
    ops = [{"op": "shift", "filter": {"phase_code": "P2"}, "days": 10}]
    planned, _ = _run_tool(db, plan, "plan_commands", {"operations": ops}, ctx=ctx)
    assert planned["ok"] is True
    result, changes = _run_tool(
        db, plan, "apply_plan_patch", {"operations": ops}, ctx=ctx
    )
    assert result["ok"] is True
    assert "P2" in changes or "T2.1" in changes
    db.commit()
    snap = plan_to_dict(db, plan)
    by_code = {t["code"]: t for t in snap["tasks"]}
    assert by_code["P2"]["start_date"] == "2026-07-11"
    assert by_code["T2.1"]["start_date"] == "2026-07-11"


def test_import_excel_without_attachment_errors(db, mini_plan):
    _user, plan = mini_plan
    job = AgentJob(plan_id=plan.id, status="queued", request_text="импортируй")
    db.add(job)
    db.flush()
    result, changes = _run_tool(
        db, plan, "import_excel_attachment", {}, job=job, ctx={}
    )
    assert result["ok"] is False
    assert result.get("errors")
    assert changes == []
