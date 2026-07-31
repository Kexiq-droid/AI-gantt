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


def test_plan_commands_over_hard_limit(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True}
    ops = [
        {"op": "shift", "filter": {"code": "T2.1"}, "days": 1}
        for _ in range(MAX_BATCH_OPS + 1)
    ]
    result, changes = _run_tool(db, plan, "plan_commands", {"operations": ops}, ctx=ctx)
    assert result["ok"] is False
    assert result["need_clarification"] is True
    assert result["count"] == MAX_BATCH_OPS + 1
    assert ctx.get("planned_ops") is None
    assert changes == []


def test_plan_commands_rejects_phases_only(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True}
    ops = [
        {
            "op": "create",
            "code": f"P{i}",
            "parent": None,
            "position": "end",
            "title": f"Phase {i}",
            "duration_days": 5,
            "predecessors": [f"P{i-1}"] if i > 1 else [],
        }
        for i in range(1, 5)
    ]
    result, _ = _run_tool(db, plan, "plan_commands", {"operations": ops}, ctx=ctx)
    assert result["ok"] is False
    assert result["reason"] == "cascade"
    assert "листов" in (result.get("message") or "").lower() or result.get("errors")


def test_plan_commands_allows_large_create_wbs(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True}
    ops = [
        {
            "op": "create",
            "code": f"T9.{i}",
            "parent": "P2",
            "title": f"Work {i}",
            "duration_days": 2,
            "predecessors": [f"T9.{i-1}"] if i > 1 else [],
        }
        for i in range(1, 8)
    ]
    result, changes = _run_tool(
        db,
        plan,
        "plan_commands",
        {"operations": ops, "plan_title": "Доп. работы P2"},
        ctx=ctx,
    )
    assert result["ok"] is True
    assert result["plan_build"] is True
    assert result["plan_title"] == "Доп. работы P2"
    assert ctx["planned_ops"][0]["op"] == "set_title"
    assert ctx["planned_ops"][0]["title"] == "Доп. работы P2"
    assert len(ctx["planned_ops"]) == 8
    assert changes == []


def test_apply_plan_build_renames_title(db, mini_plan):
    from backend.app.models import AgentJob

    _user, plan = mini_plan
    assert "VAX" in plan.title or "Mini" in plan.title or plan.title
    old_title = plan.title
    ctx: dict = {"require_plan": True}
    job = AgentJob(
        plan_id=plan.id,
        status="running",
        request_text="создай реалистичный план ремонта квартиры на 100м2",
    )
    db.add(job)
    db.flush()
    ops = [
        {
            "op": "create",
            "code": f"T9.{i}",
            "parent": "P2",
            "position": "end",
            "title": f"Work {i}",
            "duration_days": 2,
            "predecessors": [f"T9.{i-1}"] if i > 1 else ["T2.1"],
        }
        for i in range(1, 4)
    ]
    planned, _ = _run_tool(
        db,
        plan,
        "plan_commands",
        {"operations": ops, "plan_title": "Ремонт квартиры 100 м²"},
        job=job,
        ctx=ctx,
    )
    assert planned["ok"] is True
    result, _ = _run_tool(
        db,
        plan,
        "apply_plan_patch",
        {"operations": planned["operations"]},
        job=job,
        ctx=ctx,
    )
    assert result["ok"] is True
    db.commit()
    db.refresh(plan)
    assert plan.title == "Ремонт квартиры 100 м²"
    assert plan.title != old_title


def test_plan_commands_create_needs_placement(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True}
    ops = [{"op": "create", "code": "T2.9", "title": "Extra", "duration_days": 3}]
    result, _ = _run_tool(db, plan, "plan_commands", {"operations": ops}, ctx=ctx)
    assert result["ok"] is False
    assert result["need_clarification"] is True
    assert result["reason"] == "create_placement"
    assert ctx.get("planned_ops") is None


def test_plan_commands_create_ok_with_placement(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True}
    ops = [
        {
            "op": "create",
            "code": "T2.9",
            "parent": "P2",
            "after": "T2.1",
            "title": "Extra",
            "duration_days": 3,
            "predecessors": ["T2.1"],
        }
    ]
    result, _ = _run_tool(db, plan, "plan_commands", {"operations": ops}, ctx=ctx)
    assert result["ok"] is True
    assert ctx["planned_ops"] == ops


def test_plan_commands_rejects_flat_wbs_without_cascade(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True}
    ops = [
        {
            "op": "create",
            "code": f"T8.{i}",
            "parent": "P2",
            "title": f"Flat {i}",
            "duration_days": 2,
            "predecessors": [],
        }
        for i in range(1, 5)
    ]
    result, _ = _run_tool(db, plan, "plan_commands", {"operations": ops}, ctx=ctx)
    assert result["ok"] is False
    assert result["reason"] == "cascade"


def test_plan_commands_replace_needs_confirm(db, mini_plan):
    _user, plan = mini_plan
    ctx: dict = {"require_plan": True}
    ops = [
        {"op": "delete", "filter": {"all": True}},
        {
            "op": "create",
            "code": "P1",
            "parent": None,
            "position": "end",
            "title": "Phase",
            "duration_days": 5,
            "predecessors": [],
        },
        {
            "op": "create",
            "code": "T1.1",
            "parent": "P1",
            "position": "end",
            "title": "A",
            "duration_days": 2,
            "predecessors": [],
        },
        {
            "op": "create",
            "code": "T1.2",
            "parent": "P1",
            "after": "T1.1",
            "title": "B",
            "duration_days": 2,
            "predecessors": ["T1.1"],
        },
    ]
    blocked, _ = _run_tool(db, plan, "plan_commands", {"operations": ops}, ctx=ctx)
    assert blocked["need_confirmation"] is True
    assert blocked.get("replace_plan") is True
    ok, _ = _run_tool(
        db, plan, "plan_commands", {"operations": ops, "confirmed": True}, ctx=ctx
    )
    assert ok["ok"] is True


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
