"""UI action log: hidden from chat API, selective undo via agent rules."""

import json

from backend.app.models import AgentJob, ChatMessage
from backend.app.services.agent import run_agent_job
from backend.app.services.ui_actions import find_ui_action


def _ui_action_rows(db, plan_id: int) -> list[ChatMessage]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.plan_id == plan_id)
        .order_by(ChatMessage.id.asc())
        .all()
    )
    return [m for m in rows if (m.content or "").startswith("[UI_ACTION]")]


def test_patch_logs_ui_action_hidden_from_messages(login_pm, SessionLocal):
    plan = login_pm.get("/api/plans/current").json()
    task = next(t for t in plan["tasks"] if t.get("parent_id") is not None)
    r = login_pm.patch(
        f"/api/plans/tasks/{task['id']}",
        json={"title": "UIActionTitle"},
    )
    assert r.status_code == 200

    msgs = login_pm.get("/api/chat/messages").json()
    assert all(not (m.get("meta") or {}).get("hidden") for m in msgs)
    assert all(not (m.get("content") or "").startswith("[UI_ACTION]") for m in msgs)

    db = SessionLocal()
    try:
        from backend.app.models import Plan, User
        from sqlalchemy import select

        user = db.scalars(select(User).where(User.login == "pm")).first()
        plan_row = db.scalars(select(Plan).where(Plan.user_id == user.id)).first()
        ui_rows = _ui_action_rows(db, plan_row.id)
        assert ui_rows, "expected hidden UI_ACTION message in DB"
        payload = json.loads(ui_rows[-1].content[len("[UI_ACTION]") :].strip())
        assert payload["kind"] == "update"
        assert payload["id"]
        assert payload["inverse"]["operations"]
        assert any(op.get("code") == task["code"] for op in payload["inverse"]["operations"])
    finally:
        db.close()


def test_import_and_reset_seed_do_not_log_ui_action(login_pm, SessionLocal):
    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / "examples" / "plan_vax_b_demo.xlsx"
    content = example.read_bytes()

    db = SessionLocal()
    try:
        from backend.app.models import Plan, User
        from sqlalchemy import select

        user = db.scalars(select(User).where(User.login == "pm")).first()
        plan_row = db.scalars(select(Plan).where(Plan.user_id == user.id)).first()
        before = len(_ui_action_rows(db, plan_row.id))
    finally:
        db.close()

    r = login_pm.post(
        "/api/plans/current/import",
        files={
            "file": (
                "plan_vax_b_demo.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200

    db = SessionLocal()
    try:
        from backend.app.models import Plan, User
        from sqlalchemy import select

        user = db.scalars(select(User).where(User.login == "pm")).first()
        plan_row = db.scalars(select(Plan).where(Plan.user_id == user.id)).first()
        after_import = len(_ui_action_rows(db, plan_row.id))
        assert after_import == before
    finally:
        db.close()

    login_pm.post("/api/plans/current/reset-seed")
    db = SessionLocal()
    try:
        from backend.app.models import Plan, User
        from sqlalchemy import select

        user = db.scalars(select(User).where(User.login == "pm")).first()
        plan_row = db.scalars(select(Plan).where(Plan.user_id == user.id)).first()
        # reset clears chat messages
        assert _ui_action_rows(db, plan_row.id) == []
    finally:
        db.close()


def test_selective_undo_ui_action_by_id(login_pm, SessionLocal):
    plan = login_pm.get("/api/plans/current").json()
    task = next(t for t in plan["tasks"] if t["code"] == "T2.1")
    original = task["title"]
    login_pm.patch(f"/api/plans/tasks/{task['id']}", json={"title": "TempUndoTitle"})
    login_pm.patch(
        f"/api/plans/tasks/{task['id']}",
        json={"title": "KeepThisTitle"},
    )

    db = SessionLocal()
    try:
        from backend.app.models import Plan, User
        from sqlalchemy import select

        user = db.scalars(select(User).where(User.login == "pm")).first()
        plan_row = db.scalars(select(Plan).where(Plan.user_id == user.id)).first()
        ui_rows = _ui_action_rows(db, plan_row.id)
        assert len(ui_rows) >= 2
        first_payload = json.loads(ui_rows[-2].content[len("[UI_ACTION]") :].strip())
        action_id = first_payload["id"]

        job = AgentJob(
            plan_id=plan_row.id,
            status="queued",
            request_text=f"Отмени действие {action_id}",
        )
        db.add(job)
        db.commit()
        job_id = job.id
        run_agent_job(db, job_id)
        job = db.get(AgentJob, job_id)
        assert job.status == "done", job.error

        found = find_ui_action(db, plan_row.id, action_id)
        assert found is not None
        _, payload = found
        assert payload.get("undone") is True
    finally:
        db.close()

    after = login_pm.get("/api/plans/current").json()
    t21 = next(t for t in after["tasks"] if t["code"] == "T2.1")
    # First update undone → title back to original; second update still applied would
    # conflict — selective undo of first restores "TempUndoTitle" baseline then...
    # Actually: first inverse restores original; second update still in plan as KeepThisTitle
    # unless we undid first only: after first patch title=Temp, after second=Keep.
    # Undoing first applies inverse of first (title→original) overwriting Keep → original.
    assert t21["title"] == original


def test_undo_last_ui_action(login_pm, SessionLocal):
    plan = login_pm.get("/api/plans/current").json()
    task = next(t for t in plan["tasks"] if t["code"] == "T2.1")
    original = task["title"]
    login_pm.patch(f"/api/plans/tasks/{task['id']}", json={"title": "LastUiTitle"})

    db = SessionLocal()
    try:
        from backend.app.models import Plan, User
        from sqlalchemy import select

        user = db.scalars(select(User).where(User.login == "pm")).first()
        plan_row = db.scalars(select(Plan).where(Plan.user_id == user.id)).first()
        job = AgentJob(
            plan_id=plan_row.id,
            status="queued",
            request_text="Отмени последнее действие пользователя",
        )
        db.add(job)
        db.commit()
        run_agent_job(db, job.id)
        job = db.get(AgentJob, job.id)
        assert job.status == "done", job.error
    finally:
        db.close()

    after = login_pm.get("/api/plans/current").json()
    t21 = next(t for t in after["tasks"] if t["code"] == "T2.1")
    assert t21["title"] == original
