from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from backend.app.config import get_settings
from backend.app.database import engine, init_db
from backend.app.routers import auth, chat, plans
from backend.app.schemas import HealthOut
from backend.app.seed_cli import seed

settings = get_settings()
ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    # auto-seed if no users
    from backend.app.database import SessionLocal
    from backend.app.models import User
    from sqlalchemy import select

    db = SessionLocal()
    try:
        if not db.scalars(select(User.id)).first():
            db.close()
            seed()
        else:
            db.close()
    except Exception:
        db.close()
        seed()
    yield


app = FastAPI(title="BioPlan", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(plans.router)
app.include_router(chat.router)


@app.get("/api/health", response_model=HealthOut)
def health():
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    llm = "ok" if settings.llm_configured else "degraded"
    status = "ok" if db_status == "ok" else "error"
    return HealthOut(status=status, db=db_status, llm=llm)


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return {"detail": "Not Found"}
        index = FRONTEND_DIST / "index.html"
        file_path = FRONTEND_DIST / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(index)
