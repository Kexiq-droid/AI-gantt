from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user
from backend.app.database import get_db
from backend.app.models import Task, User
from backend.app.schemas import PlanOut, TaskUpdate, TasksShiftRequest
from backend.app.services.excel_io import (
    content_disposition,
    export_filename,
    export_plan_xlsx,
)
from backend.app.services.plan_store import (
    apply_imported_xlsx,
    ensure_user_plan,
    load_seed_into_plan,
    plan_to_dict,
    push_snapshot,
    restore_snapshot,
    redo_snapshot,
)
from backend.app.services.serializers import serialize_plan

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("/current", response_model=PlanOut)
def get_current_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.patch("/tasks/{task_id}", response_model=PlanOut)
def update_task(
    task_id: int,
    body: TaskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = ensure_user_plan(db, user.id)
    task = db.get(Task, task_id)
    if not task or task.plan_id != plan.id:
        raise HTTPException(404, "Задача не найдена")
    push_snapshot(db, plan, source="ui")
    data = body.model_dump(exclude_unset=True)

    if "progress_pct" in data:
        has_kids = any(t.parent_id == task.id for t in plan.tasks)
        if has_kids:
            raise HTTPException(
                400, "Прогресс фазы считается автоматически как среднее по дочерним задачам"
            )
        data["progress_pct"] = max(0, min(100, int(data["progress_pct"])))

    old_start = task.start_date
    for k, v in data.items():
        setattr(task, k, v)
    task.last_changed_by = "user"

    # Сдвиг фазы/родителя — двигаем всё поддерево на тот же delta
    if "start_date" in data and task.start_date != old_start:
        delta = (task.start_date - old_start).days
        if delta:
            by_parent: dict[int | None, list[Task]] = {}
            for t in plan.tasks:
                by_parent.setdefault(t.parent_id, []).append(t)

            def walk(parent_id: int) -> None:
                for child in by_parent.get(parent_id) or []:
                    child.start_date = child.start_date + timedelta(days=delta)
                    child.last_changed_by = "user"
                    walk(child.id)

            walk(task.id)

    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/tasks/shift", response_model=PlanOut)
def shift_tasks(
    body: TasksShiftRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Shift tasks (and their subtrees) by the same number of days. Dedupes ancestors."""
    plan = ensure_user_plan(db, user.id)
    if body.days == 0 or not body.task_ids:
        return serialize_plan(db, plan)

    by_id = {t.id: t for t in plan.tasks if t.plan_id == plan.id}
    selected = [tid for tid in body.task_ids if tid in by_id]
    if not selected:
        raise HTTPException(404, "Задачи не найдены")

    selected_set = set(selected)

    def has_selected_ancestor(tid: int) -> bool:
        cur = by_id[tid].parent_id
        while cur:
            if cur in selected_set:
                return True
            cur = by_id[cur].parent_id if cur in by_id else None
        return False

    roots = [tid for tid in selected if not has_selected_ancestor(tid)]

    by_parent: dict[int | None, list[Task]] = {}
    for t in plan.tasks:
        by_parent.setdefault(t.parent_id, []).append(t)

    push_snapshot(db, plan, source="ui")
    shifted: set[int] = set()

    def shift_subtree(root_id: int) -> None:
        stack = [root_id]
        while stack:
            tid = stack.pop()
            if tid in shifted:
                continue
            task = by_id.get(tid)
            if not task:
                continue
            task.start_date = task.start_date + timedelta(days=body.days)
            task.last_changed_by = "user"
            shifted.add(tid)
            for child in by_parent.get(tid) or []:
                stack.append(child.id)

    for rid in roots:
        shift_subtree(rid)

    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/current/import", response_model=PlanOut)
async def import_excel(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Нужен файл .xlsx")
    content = await file.read()
    if len(content) > 5_000_000:
        raise HTTPException(400, "Файл слишком большой")
    plan = ensure_user_plan(db, user.id)
    ok, errors, _codes, _title = apply_imported_xlsx(
        db, plan, content, source="excel", changed_by="user"
    )
    if not ok:
        raise HTTPException(400, "; ".join(errors) if errors else "Ошибка импорта")
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.get("/current/export")
def export_excel(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    payload = plan_to_dict(db, plan)
    data = export_plan_xlsx(payload)
    filename = export_filename(payload)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": content_disposition(filename)},
    )


@router.post("/current/undo", response_model=PlanOut)
def undo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    ok = restore_snapshot(db, plan)
    if not ok:
        raise HTTPException(400, "Нечего возвращать")
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/current/redo", response_model=PlanOut)
def redo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    ok = redo_snapshot(db, plan)
    if not ok:
        raise HTTPException(400, "Нечего применять вперёд")
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/current/reset-seed", response_model=PlanOut)
def reset_seed(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    from backend.app.models import AgentJob, ChatMessage, PlanSnapshot
    from sqlalchemy import delete

    db.execute(delete(ChatMessage).where(ChatMessage.plan_id == plan.id))
    db.execute(delete(AgentJob).where(AgentJob.plan_id == plan.id))
    db.execute(delete(PlanSnapshot).where(PlanSnapshot.plan_id == plan.id))
    load_seed_into_plan(db, plan)
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)
