"""Plan-scoped assignee catalog."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Assignee, Plan, Task


def ensure_assignee(db: Session, plan_id: int, name: str | None) -> Assignee | None:
    """Upsert assignee by name; empty names are ignored."""
    clean = (name or "").strip()
    if not clean:
        return None
    row = db.scalars(
        select(Assignee).where(Assignee.plan_id == plan_id, Assignee.name == clean)
    ).first()
    if row:
        return row
    row = Assignee(plan_id=plan_id, name=clean)
    db.add(row)
    db.flush()
    return row


def sync_assignees_from_tasks(db: Session, plan: Plan) -> None:
    """Ensure every non-empty task.assignee exists in the catalog."""
    for t in plan.tasks:
        ensure_assignee(db, plan.id, t.assignee)


def list_assignees(db: Session, plan: Plan) -> list[Assignee]:
    sync_assignees_from_tasks(db, plan)
    return list(
        db.scalars(
            select(Assignee).where(Assignee.plan_id == plan.id).order_by(Assignee.name.asc())
        ).all()
    )


def delete_assignee(db: Session, plan: Plan, assignee_id: int) -> bool:
    row = db.get(Assignee, assignee_id)
    if not row or row.plan_id != plan.id:
        return False
    name = row.name
    for t in plan.tasks:
        if (t.assignee or "").strip() == name:
            t.assignee = ""
            t.last_changed_by = "user"
    db.delete(row)
    db.flush()
    return True
