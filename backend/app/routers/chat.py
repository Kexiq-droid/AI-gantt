import asyncio
import json
import re
from collections import defaultdict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, require_editor
from backend.app.config import ROOT
from backend.app.database import SessionLocal, get_db
from backend.app.models import AgentJob, ChatMessage, User
from backend.app.schemas import (
    AgentStatsOut,
    ChatMessageOut,
    JobOut,
    RatingRequest,
)
from backend.app.services.agent import run_agent_job
from backend.app.services.plan_store import ensure_user_plan
from backend.app.services.serializers import job_to_dict
from backend.app.services.ui_actions import is_hidden_chat_meta

router = APIRouter(prefix="/api", tags=["chat"])

UPLOAD_DIR = ROOT / "data" / "chat_uploads"
MAX_UPLOAD_BYTES = 5_000_000

# Per-plan single-flight: jobs for the same plan never run in parallel.
_plan_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def _run_job_sync(job_id: int) -> None:
    db = SessionLocal()
    try:
        run_agent_job(db, job_id)
    finally:
        db.close()


async def _run_job_serialized(plan_id: int, job_id: int) -> None:
    lock = _plan_locks[plan_id]
    async with lock:
        await asyncio.to_thread(_run_job_sync, job_id)


@router.post("/chat")
async def chat(
    message: str = Form(""),
    file: UploadFile | None = File(None),
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    text = (message or "").strip()
    has_file = file is not None and bool(file.filename)

    if not text and not has_file:
        raise HTTPException(400, "Пустое сообщение")

    if has_file:
        assert file is not None
        name = file.filename or "plan.xlsx"
        if not name.lower().endswith(".xlsx"):
            raise HTTPException(400, "Нужен файл .xlsx")
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(400, "Файл слишком большой")
        if not text:
            text = f"Импортируй план из файла «{name}»"
    else:
        content = b""
        name = ""

    plan = ensure_user_plan(db, user.id)
    job = AgentJob(plan_id=plan.id, status="queued", request_text=text)
    db.add(job)
    db.flush()

    if has_file:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w.\-]+", "_", name)[:120] or "plan.xlsx"
        path = UPLOAD_DIR / f"{job.id}_{safe}"
        path.write_bytes(content)
        job.attachment_path = str(path)
        job.attachment_name = name

    meta = {"attachment_name": name} if has_file else None
    db.add(
        ChatMessage(
            plan_id=plan.id,
            role="user",
            content=text,
            job_id=job.id,
            meta_json=json.dumps(meta, ensure_ascii=False) if meta else None,
        )
    )
    db.commit()
    db.refresh(job)

    asyncio.create_task(_run_job_serialized(plan.id, job.id))
    return {"job_id": job.id}


@router.get("/chat/messages", response_model=list[ChatMessageOut])
def messages(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.plan_id == plan.id)
        .order_by(ChatMessage.id.asc())
    ).all()
    job_ids = {m.job_id for m in rows if m.job_id}
    jobs_by_id: dict[int, AgentJob] = {}
    if job_ids:
        for j in db.scalars(select(AgentJob).where(AgentJob.id.in_(job_ids))).all():
            jobs_by_id[j.id] = j

    out = []
    for m in rows:
        meta: dict | None = None
        if m.meta_json:
            try:
                meta = json.loads(m.meta_json)
            except json.JSONDecodeError:
                meta = None
        if is_hidden_chat_meta(meta):
            continue
        if m.role == "assistant" and m.job_id and m.job_id in jobs_by_id:
            rating = jobs_by_id[m.job_id].rating
            if rating:
                meta = {**(meta or {}), "rating": rating}
        out.append(
            ChatMessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                job_id=m.job_id,
                meta=meta,
                created_at=m.created_at,
            )
        )
    return out


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    job = db.get(AgentJob, job_id)
    if not job or job.plan_id != plan.id:
        raise HTTPException(404, "Job не найден")
    return JobOut(**job_to_dict(job))


@router.get("/agent/runs", response_model=list[JobOut])
def agent_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    jobs = db.scalars(
        select(AgentJob).where(AgentJob.plan_id == plan.id).order_by(AgentJob.id.desc()).limit(100)
    ).all()
    return [JobOut(**job_to_dict(j)) for j in jobs]


@router.get("/agent/stats", response_model=AgentStatsOut)
def agent_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    jobs = db.scalars(select(AgentJob).where(AgentJob.plan_id == plan.id)).all()
    total = len(jobs)
    if total == 0:
        return AgentStatsOut(
            total=0,
            success_rate=0,
            validate_fail_rate=0,
            undo_after_agent_rate=0,
            avg_latency_ms=None,
            ratings_up=0,
            ratings_down=0,
        )
    done = sum(1 for j in jobs if j.status == "done")
    vfail = sum(1 for j in jobs if j.validate_ok is False)
    undone = sum(1 for j in jobs if j.undone_within_5m)
    lat = [j.latency_ms for j in jobs if j.latency_ms is not None]
    return AgentStatsOut(
        total=total,
        success_rate=done / total,
        validate_fail_rate=vfail / total,
        undo_after_agent_rate=undone / total,
        avg_latency_ms=(sum(lat) / len(lat)) if lat else None,
        ratings_up=sum(1 for j in jobs if j.rating == "up"),
        ratings_down=sum(1 for j in jobs if j.rating == "down"),
    )


@router.post("/jobs/{job_id}/rating", response_model=JobOut)
def rate_job(
    job_id: int,
    body: RatingRequest,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    plan = ensure_user_plan(db, user.id)
    job = db.get(AgentJob, job_id)
    if not job or job.plan_id != plan.id:
        raise HTTPException(404, "Job не найден")
    job.rating = body.rating
    job.rating_comment = body.comment
    db.commit()
    db.refresh(job)
    return JobOut(**job_to_dict(job))
