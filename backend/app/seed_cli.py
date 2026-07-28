"""CLI: recreate demo users and seed plans."""

from backend.app.auth import hash_password
from backend.app.config import get_settings
from backend.app.database import SessionLocal, init_db
from backend.app.models import ChatMessage, AgentJob, PlanSnapshot, Plan, User, Dependency, Task
from backend.app.services.plan_store import ensure_user_plan, load_seed_into_plan
from sqlalchemy import select


def seed() -> None:
    init_db()
    settings = get_settings()
    db = SessionLocal()
    try:
        for login, password in (
            ("pm", settings.demo_pm_password),
            ("viewer", settings.demo_viewer_password),
        ):
            user = db.scalars(select(User).where(User.login == login)).first()
            if not user:
                user = User(login=login, password_hash=hash_password(password))
                db.add(user)
                db.flush()
            else:
                user.password_hash = hash_password(password)

            # wipe plan-related for clean seed
            plans = db.scalars(select(Plan).where(Plan.user_id == user.id)).all()
            for plan in plans:
                db.query(ChatMessage).filter(ChatMessage.plan_id == plan.id).delete()
                db.query(AgentJob).filter(AgentJob.plan_id == plan.id).delete()
                db.query(PlanSnapshot).filter(PlanSnapshot.plan_id == plan.id).delete()
                db.query(Dependency).filter(Dependency.plan_id == plan.id).delete()
                db.query(Task).filter(Task.plan_id == plan.id).delete()
                db.delete(plan)
            db.flush()
            plan = Plan(user_id=user.id, title="tmp", start_date=__import__("datetime").date.today())
            db.add(plan)
            db.flush()
            load_seed_into_plan(db, plan)
        db.commit()
        print("Seed OK: users pm/viewer + pharma plans")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
