from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import AgentJob, Dependency, Plan, PlanSnapshot, Task
from backend.app.seed_data import PLAN_START, PLAN_TITLE, SEED_TASKS, compute_schedule


def task_end(start: date, duration_days: int) -> date:
    return start + timedelta(days=max(duration_days, 0))


def plan_to_dict(db: Session, plan: Plan) -> dict[str, Any]:
    tasks = db.scalars(select(Task).where(Task.plan_id == plan.id).order_by(Task.sort_order)).all()
    deps = db.scalars(select(Dependency).where(Dependency.plan_id == plan.id)).all()
    id_to_code = {t.id: t.code for t in tasks}
    preds: dict[int, list[str]] = {t.id: [] for t in tasks}
    for d in deps:
        if d.successor_task_id in preds:
            preds[d.successor_task_id].append(id_to_code[d.predecessor_task_id])

    return {
        "title": plan.title,
        "start_date": plan.start_date.isoformat(),
        "tasks": [
            {
                "code": t.code,
                "parent": id_to_code.get(t.parent_id) if t.parent_id else None,
                "title": t.title,
                "description": t.description or "",
                "assignee": t.assignee or "",
                "duration_days": t.duration_days,
                "progress_pct": int(getattr(t, "progress_pct", 0) or 0),
                "start_date": t.start_date.isoformat(),
                "sort_order": t.sort_order,
                "last_changed_by": t.last_changed_by,
                "predecessors": preds.get(t.id, []),
            }
            for t in tasks
        ],
    }


def push_snapshot(db: Session, plan: Plan, source: str) -> None:
    """Save current plan for undo and clear redo (new edit branch)."""
    _clear_stack(db, plan.id, kind="redo")
    payload = plan_to_dict(db, plan)
    db.add(
        PlanSnapshot(
            plan_id=plan.id,
            payload_json=json.dumps(payload, ensure_ascii=False),
            source=source,
            kind="undo",
        )
    )
    db.flush()
    snaps = db.scalars(
        select(PlanSnapshot)
        .where(PlanSnapshot.plan_id == plan.id, PlanSnapshot.kind == "undo")
        .order_by(PlanSnapshot.id.desc())
    ).all()
    for old in snaps[10:]:
        db.delete(old)


def _clear_stack(db: Session, plan_id: int, *, kind: str) -> None:
    snaps = db.scalars(
        select(PlanSnapshot).where(PlanSnapshot.plan_id == plan_id, PlanSnapshot.kind == kind)
    ).all()
    for s in snaps:
        db.delete(s)
    db.flush()


def undo_count(db: Session, plan_id: int) -> int:
    return len(
        db.scalars(
            select(PlanSnapshot.id).where(
                PlanSnapshot.plan_id == plan_id, PlanSnapshot.kind == "undo"
            )
        ).all()
    )


def redo_count(db: Session, plan_id: int) -> int:
    return len(
        db.scalars(
            select(PlanSnapshot.id).where(
                PlanSnapshot.plan_id == plan_id, PlanSnapshot.kind == "redo"
            )
        ).all()
    )


def _trim_stack(db: Session, plan_id: int, *, kind: str, limit: int = 10) -> None:
    snaps = db.scalars(
        select(PlanSnapshot)
        .where(PlanSnapshot.plan_id == plan_id, PlanSnapshot.kind == kind)
        .order_by(PlanSnapshot.id.desc())
    ).all()
    for old in snaps[limit:]:
        db.delete(old)


def restore_snapshot(db: Session, plan: Plan) -> bool:
    """Undo: pop undo stack, push current to redo."""
    snap = db.scalars(
        select(PlanSnapshot)
        .where(PlanSnapshot.plan_id == plan.id, PlanSnapshot.kind == "undo")
        .order_by(PlanSnapshot.id.desc())
    ).first()
    if not snap:
        return False

    cutoff = datetime.utcnow() - timedelta(minutes=5)
    recent_jobs = db.scalars(
        select(AgentJob).where(
            AgentJob.plan_id == plan.id,
            AgentJob.status == "done",
            AgentJob.finished_at.is_not(None),
            AgentJob.finished_at >= cutoff,
        )
    ).all()
    for job in recent_jobs:
        job.undone_within_5m = True

    # current state → redo
    current = plan_to_dict(db, plan)
    db.add(
        PlanSnapshot(
            plan_id=plan.id,
            payload_json=json.dumps(current, ensure_ascii=False),
            source="undo",
            kind="redo",
        )
    )
    payload = json.loads(snap.payload_json)
    db.delete(snap)
    db.flush()
    _trim_stack(db, plan.id, kind="redo")
    _replace_plan_content(db, plan, payload, changed_by="user")
    return True


def redo_snapshot(db: Session, plan: Plan) -> bool:
    """Redo: pop redo stack, push current to undo."""
    snap = db.scalars(
        select(PlanSnapshot)
        .where(PlanSnapshot.plan_id == plan.id, PlanSnapshot.kind == "redo")
        .order_by(PlanSnapshot.id.desc())
    ).first()
    if not snap:
        return False

    current = plan_to_dict(db, plan)
    db.add(
        PlanSnapshot(
            plan_id=plan.id,
            payload_json=json.dumps(current, ensure_ascii=False),
            source="redo",
            kind="undo",
        )
    )
    payload = json.loads(snap.payload_json)
    db.delete(snap)
    db.flush()
    _trim_stack(db, plan.id, kind="undo")
    _replace_plan_content(db, plan, payload, changed_by="user")
    return True


def _replace_plan_content(
    db: Session, plan: Plan, payload: dict[str, Any], changed_by: str
) -> None:
    db.query(Dependency).filter(Dependency.plan_id == plan.id).delete()
    db.query(Task).filter(Task.plan_id == plan.id).delete()
    db.flush()

    plan.title = payload.get("title") or plan.title
    if payload.get("start_date"):
        plan.start_date = date.fromisoformat(payload["start_date"])

    code_to_id: dict[str, int] = {}
    # create tasks without parents first pass, then set parents
    for t in payload.get("tasks") or []:
        task = Task(
            plan_id=plan.id,
            code=t["code"],
            parent_id=None,
            title=t["title"],
            description=t.get("description") or "",
            assignee=t.get("assignee") or "",
            duration_days=int(t.get("duration_days") or 1),
            progress_pct=max(0, min(100, int(t.get("progress_pct") or 0))),
            start_date=date.fromisoformat(t["start_date"])
            if t.get("start_date")
            else plan.start_date,
            sort_order=int(t.get("sort_order") or 0),
            last_changed_by=t.get("last_changed_by") or changed_by,
        )
        db.add(task)
        db.flush()
        code_to_id[t["code"]] = task.id

    for t in payload.get("tasks") or []:
        parent = t.get("parent")
        if parent and parent in code_to_id:
            task = db.get(Task, code_to_id[t["code"]])
            if task:
                task.parent_id = code_to_id[parent]

    for t in payload.get("tasks") or []:
        for pred in t.get("predecessors") or []:
            if pred in code_to_id and t["code"] in code_to_id:
                db.add(
                    Dependency(
                        plan_id=plan.id,
                        predecessor_task_id=code_to_id[pred],
                        successor_task_id=code_to_id[t["code"]],
                    )
                )
    db.flush()


def load_seed_into_plan(db: Session, plan: Plan) -> None:
    rows = []
    for code, parent, title, desc, assignee, dur, preds, sort in SEED_TASKS:
        rows.append(
            {
                "code": code,
                "parent": parent,
                "title": title,
                "description": desc,
                "assignee": assignee,
                "duration_days": dur,
                "predecessors": preds,
                "sort_order": sort,
            }
        )
    starts = compute_schedule(rows, PLAN_START)
    for r in rows:
        r["start_date"] = starts[r["code"]].isoformat()
        r["last_changed_by"] = "user"
    payload = {"title": PLAN_TITLE, "start_date": PLAN_START.isoformat(), "tasks": rows}
    plan.title = PLAN_TITLE
    plan.start_date = PLAN_START
    _replace_plan_content(db, plan, payload, changed_by="user")


def ensure_user_plan(db: Session, user_id: int) -> Plan:
    plan = db.scalars(select(Plan).where(Plan.user_id == user_id)).first()
    if plan:
        return plan
    plan = Plan(user_id=user_id, title=PLAN_TITLE, start_date=PLAN_START)
    db.add(plan)
    db.flush()
    load_seed_into_plan(db, plan)
    return plan


def apply_imported_xlsx(
    db: Session,
    plan: Plan,
    content: bytes,
    *,
    source: str = "excel",
    changed_by: str = "user",
) -> tuple[bool, list[str], list[str], str]:
    """Import .xlsx bytes into plan. Returns (ok, errors, task_codes, title)."""
    from backend.app.services.excel_io import import_plan_xlsx
    from backend.app.services.validate import validate_plan_dict

    try:
        payload = import_plan_xlsx(content, plan_start=plan.start_date)
    except Exception as exc:  # noqa: BLE001
        return False, [f"Ошибка импорта: {exc}"], [], ""
    errors = validate_plan_dict(payload)
    if errors:
        return False, errors, [], ""
    push_snapshot(db, plan, source=source)
    _replace_plan_content(db, plan, payload, changed_by=changed_by)
    db.flush()
    codes = [str(t.get("code")) for t in (payload.get("tasks") or []) if t.get("code")]
    title = str(payload.get("title") or plan.title or "")
    return True, [], codes, title
