"""CLI: recreate demo users and seed plans."""

from backend.app.auth import hash_password
from backend.app.config import get_settings
from backend.app.database import SessionLocal, init_db
from backend.app.models import ChatMessage, AgentJob, PlanSnapshot, Plan, User, Dependency, Task, Assignee
from backend.app.services.plan_store import load_seed_into_plan
from sqlalchemy import select


def _wipe_user_plans(db, user: User) -> None:
    plans = db.scalars(select(Plan).where(Plan.user_id == user.id)).all()
    for plan in plans:
        db.query(ChatMessage).filter(ChatMessage.plan_id == plan.id).delete()
        db.query(AgentJob).filter(AgentJob.plan_id == plan.id).delete()
        db.query(PlanSnapshot).filter(PlanSnapshot.plan_id == plan.id).delete()
        db.query(Dependency).filter(Dependency.plan_id == plan.id).delete()
        db.query(Assignee).filter(Assignee.plan_id == plan.id).delete()
        db.query(Task).filter(Task.plan_id == plan.id).delete()
        db.delete(plan)
    db.flush()


def seed() -> None:
    init_db()
    settings = get_settings()
    db = SessionLocal()
    try:
        # Remove legacy viewer account if present
        legacy = db.scalars(select(User).where(User.login == "viewer")).first()
        if legacy:
            _wipe_user_plans(db, legacy)
            db.delete(legacy)
            db.flush()

        user = db.scalars(select(User).where(User.login == "pm")).first()
        if not user:
            user = User(
                login="pm",
                password_hash=hash_password(settings.demo_pm_password),
                role="editor",
            )
            db.add(user)
            db.flush()
        else:
            user.password_hash = hash_password(settings.demo_pm_password)
            user.role = "editor"

        _wipe_user_plans(db, user)
        plan = Plan(
            user_id=user.id,
            title="tmp",
            start_date=__import__("datetime").date.today(),
        )
        db.add(plan)
        db.flush()
        load_seed_into_plan(db, plan)
        db.commit()
        print("Seed OK: user pm + pharma plan")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
