from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from backend.app.models import Dependency, Plan, Task
from backend.app.schemas import DependencyOut, PlanOut, TaskOut
from backend.app.services.plan_store import task_end, undo_count, redo_count


def serialize_plan(db: Session, plan: Plan) -> PlanOut:
    tasks = sorted(plan.tasks, key=lambda t: t.sort_order)
    deps = plan.dependencies
    id_to_code = {t.id: t.code for t in tasks}
    preds: dict[int, list[str]] = {t.id: [] for t in tasks}
    for d in deps:
        preds.setdefault(d.successor_task_id, []).append(id_to_code.get(d.predecessor_task_id, "?"))

    children: dict[int, list[Task]] = {}
    for t in tasks:
        if t.parent_id:
            children.setdefault(t.parent_id, []).append(t)

    progress_cache: dict[int, int] = {}

    def effective_progress(task: Task) -> int:
        if task.id in progress_cache:
            return progress_cache[task.id]
        kids = children.get(task.id) or []
        if not kids:
            val = max(0, min(100, int(getattr(task, "progress_pct", 0) or 0)))
        else:
            vals = [effective_progress(c) for c in kids]
            val = int(round(sum(vals) / len(vals))) if vals else 0
        progress_cache[task.id] = val
        return val

    task_outs = []
    for t in tasks:
        task_outs.append(
            TaskOut(
                id=t.id,
                code=t.code,
                parent_id=t.parent_id,
                parent_code=id_to_code.get(t.parent_id) if t.parent_id else None,
                title=t.title,
                description=t.description or "",
                assignee=t.assignee or "",
                duration_days=t.duration_days,
                progress_pct=effective_progress(t),
                start_date=t.start_date,
                end_date=task_end(t.start_date, t.duration_days),
                sort_order=t.sort_order,
                last_changed_by=t.last_changed_by,
                updated_at=t.updated_at,
                predecessor_codes=preds.get(t.id, []),
                has_children=bool(children.get(t.id)),
            )
        )

    dep_outs = [
        DependencyOut(
            id=d.id,
            predecessor_task_id=d.predecessor_task_id,
            successor_task_id=d.successor_task_id,
            predecessor_code=id_to_code.get(d.predecessor_task_id, ""),
            successor_code=id_to_code.get(d.successor_task_id, ""),
        )
        for d in deps
    ]

    return PlanOut(
        id=plan.id,
        title=plan.title,
        start_date=plan.start_date,
        updated_at=plan.updated_at,
        tasks=task_outs,
        dependencies=dep_outs,
        undo_count=undo_count(db, plan.id),
        redo_count=redo_count(db, plan.id),
    )


def job_to_dict(job) -> dict:
    changes = []
    validate_errors = []
    tool_calls = []
    if job.changes_json:
        try:
            changes = json.loads(job.changes_json)
        except json.JSONDecodeError:
            changes = []
    if job.validate_errors_json:
        try:
            validate_errors = json.loads(job.validate_errors_json)
        except json.JSONDecodeError:
            validate_errors = []
    if job.tool_calls_json:
        try:
            tool_calls = json.loads(job.tool_calls_json)
        except json.JSONDecodeError:
            tool_calls = []
    return {
        "id": job.id,
        "plan_id": job.plan_id,
        "status": job.status,
        "request_text": job.request_text,
        "result_summary": job.result_summary,
        "error": job.error,
        "changes": changes,
        "provider": job.provider,
        "model": job.model,
        "latency_ms": job.latency_ms,
        "validate_ok": job.validate_ok,
        "validate_errors": validate_errors,
        "tool_calls": tool_calls,
        "tokens_input": job.tokens_input,
        "tokens_output": job.tokens_output,
        "undone_within_5m": job.undone_within_5m,
        "rating": job.rating,
        "rating_comment": job.rating_comment,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }
