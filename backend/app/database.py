from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _sqlite_fk(dbapi_conn, _):
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from backend.app import models  # noqa: F401
    from sqlalchemy import inspect, text

    Path = __import__("pathlib").Path
    if settings.database_url.startswith("sqlite:///"):
        path = settings.database_url.replace("sqlite:///", "", 1)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    # lightweight migrate: plan_snapshots.kind + agent_jobs attachments
    try:
        insp = inspect(engine)
        if "plan_snapshots" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("plan_snapshots")}
            if "kind" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE plan_snapshots ADD COLUMN kind VARCHAR(8) "
                            "DEFAULT 'undo'"
                        )
                    )
                    conn.execute(
                        text("UPDATE plan_snapshots SET kind = 'undo' WHERE kind IS NULL")
                    )
        if "agent_jobs" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("agent_jobs")}
            with engine.begin() as conn:
                if "attachment_path" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE agent_jobs ADD COLUMN attachment_path VARCHAR(512)"
                        )
                    )
                if "attachment_name" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE agent_jobs ADD COLUMN attachment_name VARCHAR(255)"
                        )
                    )
        if "tasks" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("tasks")}
            if "progress_pct" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE tasks ADD COLUMN progress_pct INTEGER DEFAULT 0"
                        )
                    )
                    conn.execute(
                        text("UPDATE tasks SET progress_pct = 0 WHERE progress_pct IS NULL")
                    )
        if "users" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("users")}
            if "role" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE users ADD COLUMN role VARCHAR(16) "
                            "DEFAULT 'editor'"
                        )
                    )
                    conn.execute(
                        text("UPDATE users SET role = 'editor' WHERE role IS NULL")
                    )
                    conn.execute(
                        text("UPDATE users SET role = 'viewer' WHERE login = 'viewer'")
                    )
                    conn.execute(
                        text("UPDATE users SET role = 'editor' WHERE login = 'pm'")
                    )
    except Exception:
        pass
