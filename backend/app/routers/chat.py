import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user
from backend.app.database import SessionLocal, get_db
from backend.app.models import AgentJob, ChatMessage, User
from backend.app.schemas import (
    AgentStatsOut,
    ChatMessageOut,
    ChatRequest,
    JobOut,
    RatingRequest,
)
from backend.app.services.agent import run_agent_job
from backend.app.services.plan_store import ensure_user_plan
from backend.app.services.serializers import job_to_dict

router = APIRouter(prefix="/api", tags=["chat"])


def _spawn_job(job_id: int) -> None:
    async def _runner():
        await asyncio.to_thread(_run_sync, job_id)

    def _run_sync(jid: int):
        db = SessionLocal()
        try:
            run_agent_job(db, jid)
        finally:
            db.close()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_runner())
        else:
            loop.run_until_complete(_runner())
    except RuntimeError:
        asyncio.get_event_loop().create_task(_runner())


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.message.strip():
        raise HTTPException(400, "Пустое сообщение")
    plan = ensure_user_plan(db, user.id)
    job = AgentJob(plan_id=plan.id, status="queued", request_text=body.message.strip())
    db.add(job)
    db.flush()
    db.add(
        ChatMessage(
            plan_id=plan.id,
            role="user",
            content=body.message.strip(),
            job_id=job.id,
        )
    )
    db.commit()
    db.refresh(job)

    async def _bg():
        await asyncio.to_thread(_sync, job.id)

    def _sync(jid: int):
        s = SessionLocal()
        try:
            run_agent_job(s, jid)
        finally:
            s.close()

    asyncio.create_task(_bg())
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
    user: User = Depends(get_current_user),
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
