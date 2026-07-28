from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user
from backend.app.database import get_db
from backend.app.models import Task, User
from backend.app.schemas import PlanOut, TaskUpdate
from backend.app.services.excel_io import export_plan_xlsx, import_plan_xlsx
from backend.app.services.plan_store import (
    ensure_user_plan,
    load_seed_into_plan,
    plan_to_dict,
    push_snapshot,
    restore_snapshot,
    _replace_plan_content,
)
from backend.app.services.serializers import serialize_plan
from backend.app.services.validate import validate_plan_dict

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
    for k, v in data.items():
        setattr(task, k, v)
    task.last_changed_by = "user"
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
    try:
        payload = import_plan_xlsx(content, plan_start=plan.start_date)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Ошибка импорта: {exc}") from exc
    errors = validate_plan_dict(payload)
    if errors:
        raise HTTPException(400, "; ".join(errors))
    push_snapshot(db, plan, source="excel")
    _replace_plan_content(db, plan, payload, changed_by="user")
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.get("/current/export")
def export_excel(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    data = export_plan_xlsx(plan_to_dict(db, plan))
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="bioplan.xlsx"'},
    )


@router.post("/current/undo", response_model=PlanOut)
def undo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    ok = restore_snapshot(db, plan)
    if not ok:
        raise HTTPException(400, "Нечего отменять")
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
