"""HTTP chat: job create, rules fallback, import, undo, rating — no live LLM."""

from pathlib import Path

import pytest

from backend.app.models import AgentJob, ChatMessage
from backend.app.services.agent import run_agent_job

EXAMPLE_XLSX = Path(__file__).resolve().parents[2] / "examples" / "plan_biokad_demo.xlsx"


@pytest.fixture()
def no_llm(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("backend.app.services.agent._client", lambda: None)


@pytest.fixture()
def no_chat_bg(monkeypatch: pytest.MonkeyPatch):
    """Disable /api/chat background tasks — tests call run_agent_job sync."""

    def _noop(coro):  # noqa: ANN001
        coro.close()
        return None

    monkeypatch.setattr("backend.app.routers.chat.asyncio.create_task", _noop)


def test_chat_returns_job_id(login_pm, SessionLocal, no_llm, no_chat_bg):
    r = login_pm.post("/api/chat", data={"message": "привет"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    assert isinstance(job_id, int)

    db = SessionLocal()
    try:
        msg = db.query(ChatMessage).filter(ChatMessage.job_id == job_id).first()
        assert msg is not None
        assert msg.role == "user"
        assert "привет" in msg.content
        job = db.get(AgentJob, job_id)
        assert job is not None
        assert job.status == "queued"
    finally:
        db.close()


def test_rules_fallback_shift_preclinical(login_pm, SessionLocal, no_llm):
    plan_before = login_pm.get("/api/plans/current").json()
    t21 = next(t for t in plan_before["tasks"] if t["code"] == "T2.1")
    old_start = t21["start_date"]

    db = SessionLocal()
    try:
        from backend.app.models import Plan, User
        from sqlalchemy import select

        user = db.scalars(select(User).where(User.login == "pm")).first()
        plan = db.scalars(select(Plan).where(Plan.user_id == user.id)).first()
        job = AgentJob(
            plan_id=plan.id,
            status="queued",
            request_text="Сдвинь всю доклинику на 10 дней",
        )
        db.add(job)
        db.commit()
        job_id = job.id
        run_agent_job(db, job_id)
        job = db.get(AgentJob, job_id)
        assert job.status == "done", job.error
    finally:
        db.close()

    plan_after = login_pm.get("/api/plans/current").json()
    t21b = next(t for t in plan_after["tasks"] if t["code"] == "T2.1")
    assert t21b["start_date"] != old_start


def test_multipart_import_via_chat(login_pm, SessionLocal, no_llm, no_chat_bg, tmp_path):
    content = EXAMPLE_XLSX.read_bytes()
    r = login_pm.post(
        "/api/chat",
        data={"message": "импортируй"},
        files={
            "file": (
                "plan_biokad_demo.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    db = SessionLocal()
    try:
        job = db.get(AgentJob, job_id)
        assert job.attachment_path
        assert Path(job.attachment_path).is_file()
        run_agent_job(db, job_id)
        db.refresh(job)
        assert job.status == "done", job.error
        assert job.provider == "rules"
    finally:
        db.close()

    plan = login_pm.get("/api/plans/current").json()
    assert len(plan["tasks"]) > 0


def test_chat_undo(login_pm, SessionLocal, no_llm):
    plan = login_pm.get("/api/plans/current").json()
    task = next(t for t in plan["tasks"] if t.get("parent_id") is not None)
    original = task["title"]
    login_pm.patch(f"/api/plans/tasks/{task['id']}", json={"title": "ChatUndo"})

    db = SessionLocal()
    try:
        from backend.app.models import Plan, User
        from sqlalchemy import select

        user = db.scalars(select(User).where(User.login == "pm")).first()
        plan_row = db.scalars(select(Plan).where(Plan.user_id == user.id)).first()
        job = AgentJob(plan_id=plan_row.id, status="queued", request_text="отмени")
        db.add(job)
        db.commit()
        run_agent_job(db, job.id)
        job = db.get(AgentJob, job.id)
        assert job.status == "done", job.error
    finally:
        db.close()

    restored = next(
        t for t in login_pm.get("/api/plans/current").json()["tasks"] if t["code"] == task["code"]
    )
    assert restored["title"] == original


def test_rating_endpoint(login_pm, SessionLocal, no_llm):
    db = SessionLocal()
    try:
        from backend.app.models import Plan, User
        from sqlalchemy import select

        user = db.scalars(select(User).where(User.login == "pm")).first()
        plan = db.scalars(select(Plan).where(Plan.user_id == user.id)).first()
        job = AgentJob(plan_id=plan.id, status="done", request_text="x")
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    r = login_pm.post(
        f"/api/jobs/{job_id}/rating",
        json={"rating": "up", "comment": "ok"},
    )
    assert r.status_code == 200
    assert r.json()["rating"] == "up"
