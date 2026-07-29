from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, require_editor
from backend.app.database import get_db
from backend.app.models import Dependency, Task, User
from backend.app.schemas import (
    AssigneeCreate,
    AssigneeOut,
    PlanOut,
    TaskCreate,
    TaskUpdate,
    TasksReorderRequest,
    TasksShiftRequest,
)
from backend.app.services.assignees import (
    delete_assignee,
    ensure_assignee,
    list_assignees,
)
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
from backend.app.services.ui_actions import log_ui_action

router = APIRouter(prefix="/api/plans", tags=["plans"])


def _pred_codes(db: Session, plan_id: int, task_id: int) -> list[str]:
    deps = db.query(Dependency).filter(
        Dependency.plan_id == plan_id,
        Dependency.successor_task_id == task_id,
    ).all()
    by_id = {t.id: t for t in db.query(Task).filter(Task.plan_id == plan_id).all()}
    out: list[str] = []
    for d in deps:
        pred = by_id.get(d.predecessor_task_id)
        if pred:
            out.append(pred.code)
    return out


def _parent_code(task: Task, by_id: dict[int, Task]) -> str | None:
    if task.parent_id and task.parent_id in by_id:
        return by_id[task.parent_id].code
    return None


def _siblings(plan_tasks: list[Task], parent_id: int | None) -> list[Task]:
    sibs = [t for t in plan_tasks if t.parent_id == parent_id]
    sibs.sort(key=lambda t: (t.sort_order, t.id))
    return sibs


def _renumber(sibs: list[Task]) -> None:
    for i, t in enumerate(sibs):
        t.sort_order = (i + 1) * 10
        t.last_changed_by = "user"


def _unique_code(plan_tasks: list[Task], preferred: str | None, parent: Task | None) -> str:
    used = {t.code for t in plan_tasks}
    if preferred:
        code = preferred.strip()
        if not code:
            raise HTTPException(400, "Пустой код задачи")
        if code in used:
            raise HTTPException(400, f"Код {code} уже существует")
        return code
    if parent:
        base = parent.code
        n = 1
        while f"{base}.{n}" in used:
            n += 1
        return f"{base}.{n}"
    n = 1
    while f"T{n}" in used:
        n += 1
    return f"T{n}"


@router.get("/current", response_model=PlanOut)
def get_current_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/tasks", response_model=PlanOut)
def create_task(
    body: TaskCreate,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    plan = ensure_user_plan(db, user.id)
    tasks = list(plan.tasks)
    parent: Task | None = None
    parent_id = body.parent_id

    if body.after_task_id is not None:
        after = db.get(Task, body.after_task_id)
        if not after or after.plan_id != plan.id:
            raise HTTPException(404, "after_task_id не найден")
        if parent_id is None:
            parent_id = after.parent_id
        elif parent_id != after.parent_id:
            raise HTTPException(400, "after_task_id должен быть sibling того же родителя")

    if parent_id is not None:
        parent = db.get(Task, parent_id)
        if not parent or parent.plan_id != plan.id:
            raise HTTPException(404, "Родитель не найден")

    code = _unique_code(tasks, body.code, parent)
    if body.start_date is not None:
        start = body.start_date
    else:
        start = parent.start_date if parent else plan.start_date

    push_snapshot(db, plan, source="ui")
    sibs = _siblings(tasks, parent_id)
    if body.after_task_id is not None:
        idx = next((i for i, t in enumerate(sibs) if t.id == body.after_task_id), len(sibs) - 1)
        insert_at = idx + 1
    else:
        insert_at = len(sibs)

    new_task = Task(
        plan_id=plan.id,
        code=code,
        parent_id=parent_id,
        title=body.title.strip(),
        description=body.description or "",
        assignee=body.assignee or "",
        duration_days=int(body.duration_days),
        progress_pct=0,
        start_date=start,
        sort_order=0,
        last_changed_by="user",
    )
    db.add(new_task)
    db.flush()
    ensure_assignee(db, plan.id, new_task.assignee)
    sibs.insert(insert_at, new_task)
    _renumber(sibs)
    parent_code = parent.code if parent else None
    log_ui_action(
        db,
        plan,
        kind="create",
        summary=f"create {code} «{new_task.title}»"
        + (f" under {parent_code}" if parent_code else ""),
        changes=[code],
        forward={
            "code": code,
            "parent": parent_code,
            "after_task_id": body.after_task_id,
            "title": new_task.title,
        },
        inverse_ops=[{"op": "delete", "code": code}],
    )
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/tasks/reorder", response_model=PlanOut)
def reorder_tasks(
    body: TasksReorderRequest,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    if body.before_task_id is None and body.after_task_id is None:
        raise HTTPException(400, "Нужен before_task_id или after_task_id")
    if body.before_task_id is not None and body.after_task_id is not None:
        raise HTTPException(400, "Укажите только before_task_id или after_task_id")

    plan = ensure_user_plan(db, user.id)
    task = db.get(Task, body.task_id)
    if not task or task.plan_id != plan.id:
        raise HTTPException(404, "Задача не найдена")

    anchor_id = body.before_task_id if body.before_task_id is not None else body.after_task_id
    anchor = db.get(Task, anchor_id)
    if not anchor or anchor.plan_id != plan.id:
        raise HTTPException(404, "Якорная задача не найдена")
    if anchor.parent_id != task.parent_id:
        raise HTTPException(400, "Можно менять порядок только среди задач одного родителя")
    if anchor.id == task.id:
        return serialize_plan(db, plan)

    push_snapshot(db, plan, source="ui")
    sibs_before = _siblings(list(plan.tasks), task.parent_id)
    order_before = [t.code for t in sibs_before]
    sibs = [t for t in sibs_before if t.id != task.id]
    if body.before_task_id is not None:
        idx = next(i for i, t in enumerate(sibs) if t.id == body.before_task_id)
        sibs.insert(idx, task)
    else:
        idx = next(i for i, t in enumerate(sibs) if t.id == body.after_task_id)
        sibs.insert(idx + 1, task)
    _renumber(sibs)
    order_after = [t.code for t in sibs]
    # inverse: restore previous sibling sort_order
    inverse = [
        {"op": "update", "code": code, "sort_order": (i + 1) * 10}
        for i, code in enumerate(order_before)
    ]
    log_ui_action(
        db,
        plan,
        kind="reorder",
        summary=f"reorder {task.code} ({' → '.join(order_after)})",
        changes=[task.code],
        forward={"code": task.code, "order_before": order_before, "order_after": order_after},
        inverse_ops=inverse,
    )
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.delete("/tasks/{task_id}", response_model=PlanOut)
def delete_task(
    task_id: int,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    plan = ensure_user_plan(db, user.id)
    task = db.get(Task, task_id)
    if not task or task.plan_id != plan.id:
        raise HTTPException(404, "Задача не найдена")
    children = [t for t in plan.tasks if t.parent_id == task.id]
    if children:
        raise HTTPException(
            400,
            f"Нельзя удалить {task.code}: есть дочерние задачи. Сначала удалите их.",
        )

    push_snapshot(db, plan, source="ui")
    by_id = {t.id: t for t in plan.tasks}
    parent_code = _parent_code(task, by_id)
    preds = _pred_codes(db, plan.id, task.id)
    snapshot = {
        "code": task.code,
        "parent": parent_code,
        "title": task.title,
        "description": task.description or "",
        "assignee": task.assignee or "",
        "duration_days": task.duration_days,
        "progress_pct": task.progress_pct,
        "start_date": task.start_date.isoformat(),
        "sort_order": task.sort_order,
        "predecessors": preds,
    }
    code = task.code
    db.query(Dependency).filter(
        Dependency.plan_id == plan.id,
        or_(
            Dependency.predecessor_task_id == task_id,
            Dependency.successor_task_id == task_id,
        ),
    ).delete(synchronize_session=False)
    db.delete(task)
    log_ui_action(
        db,
        plan,
        kind="delete",
        summary=f"delete {code}",
        changes=[code],
        forward={"code": code},
        inverse_ops=[{"op": "create", **snapshot}],
    )
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.patch("/tasks/{task_id}", response_model=PlanOut)
def update_task(
    task_id: int,
    body: TaskUpdate,
    user: User = Depends(require_editor),
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

    # Capture before-state for selective undo
    field_keys = (
        "title",
        "description",
        "assignee",
        "duration_days",
        "start_date",
        "progress_pct",
    )
    before: dict = {}
    for k in field_keys:
        if k in data:
            val = getattr(task, k)
            before[k] = val.isoformat() if hasattr(val, "isoformat") else val

    old_start = task.start_date
    for k, v in data.items():
        setattr(task, k, v)
    task.last_changed_by = "user"
    if "assignee" in data:
        ensure_assignee(db, plan.id, task.assignee)

    subtree_codes = [task.code]
    # Сдвиг фазы/родителя — двигаем всё поддерево на тот же delta
    delta = 0
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
                    subtree_codes.append(child.code)
                    walk(child.id)

            walk(task.id)

    inverse_ops: list[dict] = []
    if before:
        inv = {"op": "update", "code": task.code, **before}
        inverse_ops.append(inv)
    if delta:
        # restore children that were shifted with parent (parent start restored above)
        for code in subtree_codes[1:]:
            inverse_ops.append({"op": "shift", "filter": {"code": code}, "days": -delta})

    changed = list(dict.fromkeys(subtree_codes))
    summary_bits = [f"{k}→{data[k]}" for k in data if k in field_keys]
    log_ui_action(
        db,
        plan,
        kind="update",
        summary=f"update {task.code} ({', '.join(summary_bits) or 'fields'})",
        changes=changed,
        forward={"code": task.code, "fields": {k: data[k] for k in data if k in field_keys}},
        inverse_ops=inverse_ops,
    )
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/tasks/shift", response_model=PlanOut)
def shift_tasks(
    body: TasksShiftRequest,
    user: User = Depends(require_editor),
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
    root_codes = [by_id[rid].code for rid in roots if rid in by_id]

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

    changed_codes = [by_id[tid].code for tid in shifted if tid in by_id]
    # Inverse: shift every moved task back (patch shift is not subtree-aware)
    inverse_ops = [
        {"op": "shift", "filter": {"codes": changed_codes}, "days": -body.days}
    ] if changed_codes else []
    log_ui_action(
        db,
        plan,
        kind="shift",
        summary=f"shift {', '.join(root_codes)} by {body.days}d",
        changes=changed_codes,
        forward={"codes": root_codes, "days": body.days},
        inverse_ops=inverse_ops,
    )
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/current/import", response_model=PlanOut)
async def import_excel(
    file: UploadFile = File(...),
    user: User = Depends(require_editor),
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
def undo(user: User = Depends(require_editor), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    ok = restore_snapshot(db, plan)
    if not ok:
        raise HTTPException(400, "Нечего возвращать")
    log_ui_action(
        db,
        plan,
        kind="undo_stack",
        summary="UI undo (snapshot stack)",
        changes=[],
        forward={},
        inverse_ops=[],
    )
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/current/redo", response_model=PlanOut)
def redo(user: User = Depends(require_editor), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    ok = redo_snapshot(db, plan)
    if not ok:
        raise HTTPException(400, "Нечего применять вперёд")
    log_ui_action(
        db,
        plan,
        kind="redo_stack",
        summary="UI redo (snapshot stack)",
        changes=[],
        forward={},
        inverse_ops=[],
    )
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.get("/assignees", response_model=list[AssigneeOut])
def get_assignees(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    rows = list_assignees(db, plan)
    db.commit()
    return rows


@router.post("/assignees", response_model=AssigneeOut)
def create_assignee(
    body: AssigneeCreate,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    plan = ensure_user_plan(db, user.id)
    name = (body.name or "").strip()
    existed = False
    if name:
        from backend.app.models import Assignee
        from sqlalchemy import select

        existed = (
            db.scalars(
                select(Assignee).where(Assignee.plan_id == plan.id, Assignee.name == name)
            ).first()
            is not None
        )
    row = ensure_assignee(db, plan.id, body.name)
    if not row:
        raise HTTPException(400, "Пустое имя исполнителя")
    if not existed:
        log_ui_action(
            db,
            plan,
            kind="assignee_create",
            summary=f"assignee create «{row.name}»",
            changes=[],
            forward={"name": row.name},
            inverse_ops=[],
        )
    db.commit()
    db.refresh(row)
    return row


@router.delete("/assignees/{assignee_id}")
def remove_assignee(
    assignee_id: int,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    plan = ensure_user_plan(db, user.id)
    from backend.app.models import Assignee

    row = db.get(Assignee, assignee_id)
    if not row or row.plan_id != plan.id:
        raise HTTPException(404, "Исполнитель не найден")
    name = row.name
    affected = [
        t.code for t in plan.tasks if (t.assignee or "").strip() == name
    ]
    ok = delete_assignee(db, plan, assignee_id)
    if not ok:
        raise HTTPException(404, "Исполнитель не найден")
    inverse = [
        {"op": "reassign", "filter": {"code": code}, "assignee": name}
        for code in affected
    ]
    log_ui_action(
        db,
        plan,
        kind="assignee_delete",
        summary=f"assignee delete «{name}»",
        changes=affected,
        forward={"name": name, "cleared_codes": affected},
        inverse_ops=inverse,
    )
    db.commit()
    return {"ok": True}


@router.post("/current/reset-seed", response_model=PlanOut)
def reset_seed(user: User = Depends(require_editor), db: Session = Depends(get_db)):
    plan = ensure_user_plan(db, user.id)
    from backend.app.models import AgentJob, Assignee, ChatMessage, PlanSnapshot
    from sqlalchemy import delete

    db.execute(delete(ChatMessage).where(ChatMessage.plan_id == plan.id))
    db.execute(delete(AgentJob).where(AgentJob.plan_id == plan.id))
    db.execute(delete(PlanSnapshot).where(PlanSnapshot.plan_id == plan.id))
    db.execute(delete(Assignee).where(Assignee.plan_id == plan.id))
    load_seed_into_plan(db, plan)
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)
