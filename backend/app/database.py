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

    # lightweight migrate: plan_snapshots.kind
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
    except Exception:
        pass
