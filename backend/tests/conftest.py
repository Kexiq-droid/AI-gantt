"""Shared pytest fixtures: temp SQLite, seed, TestClient, login helper."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import hash_password
from backend.app.config import get_settings
from backend.app.database import Base, get_db
from backend.app.models import Plan, User
from backend.app.services.plan_store import load_seed_into_plan


EXAMPLE_XLSX = Path(__file__).resolve().parents[2] / "examples" / "plan_biokad_demo.xlsx"


@pytest.fixture()
def engine(tmp_path: Path):
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"
    eng = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _fk(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    import backend.app.models  # noqa: F401

    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def SessionLocal(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db(SessionLocal) -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded_db(db: Session) -> Session:
    """Users pm/viewer + full seed plan for each."""
    settings = get_settings()
    for login, password in (
        ("pm", settings.demo_pm_password),
        ("viewer", settings.demo_viewer_password),
    ):
        user = User(login=login, password_hash=hash_password(password))
        db.add(user)
        db.flush()
        plan = Plan(user_id=user.id, title="tmp", start_date=__import__("datetime").date.today())
        db.add(plan)
        db.flush()
        load_seed_into_plan(db, plan)
    db.commit()
    return db


@pytest.fixture()
def mini_plan(db: Session) -> tuple[User, Plan]:
    """One user + small plan (2–3 tasks) for tool-level tests."""
    from datetime import date

    from backend.app.models import Task

    user = User(login="tooluser", password_hash=hash_password("secret"))
    db.add(user)
    db.flush()
    plan = Plan(user_id=user.id, title="Mini", start_date=date(2026, 7, 1))
    db.add(plan)
    db.flush()
    p2 = Task(
        plan_id=plan.id,
        code="P2",
        parent_id=None,
        title="Доклиника",
        description="",
        assignee="",
        duration_days=10,
        start_date=date(2026, 7, 1),
        sort_order=1,
        last_changed_by="user",
    )
    db.add(p2)
    db.flush()
    t21 = Task(
        plan_id=plan.id,
        code="T2.1",
        parent_id=p2.id,
        title="In vitro",
        description="",
        assignee="Петрова",
        duration_days=5,
        start_date=date(2026, 7, 1),
        sort_order=2,
        last_changed_by="user",
    )
    t22 = Task(
        plan_id=plan.id,
        code="T2.2",
        parent_id=p2.id,
        title="Tox",
        description="",
        assignee="Иванов",
        duration_days=5,
        start_date=date(2026, 7, 8),
        sort_order=3,
        last_changed_by="user",
    )
    db.add_all([t21, t22])
    db.commit()
    db.refresh(plan)
    return user, plan


@pytest.fixture()
def app(engine, SessionLocal, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """FastAPI app without production lifespan; DB wired to temp SQLite."""
    monkeypatch.setattr("backend.app.database.engine", engine)
    monkeypatch.setattr("backend.app.database.SessionLocal", SessionLocal)
    monkeypatch.setattr("backend.app.routers.chat.SessionLocal", SessionLocal)
    monkeypatch.setattr("backend.app.auth.settings.cookie_secure", False)

    from backend.app.routers import auth, chat, plans

    test_app = FastAPI(title="BioPlan-Test")
    test_app.include_router(auth.router)
    test_app.include_router(plans.router)
    test_app.include_router(chat.router)

    def override_get_db() -> Generator[Session, None, None]:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture()
def client(app: FastAPI, seeded_db: Session) -> Generator[TestClient, None, None]:
    """HTTP client against seeded temp DB (pm / viewer)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def login_pm(client: TestClient) -> TestClient:
    settings = get_settings()
    r = client.post(
        "/api/auth/login",
        json={"login": "pm", "password": settings.demo_pm_password},
    )
    assert r.status_code == 200, r.text
    return client
