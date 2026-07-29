"""Plan store: undo/redo, import xlsx, seed dates."""

from datetime import date
from pathlib import Path

from backend.app.models import Task
from backend.app.seed_data import PLAN_START
from backend.app.services.plan_store import (
    apply_imported_xlsx,
    load_seed_into_plan,
    plan_to_dict,
    push_snapshot,
    redo_snapshot,
    restore_snapshot,
)

EXAMPLE_XLSX = Path(__file__).resolve().parents[2] / "examples" / "plan_biokad_demo.xlsx"


def test_undo_restores_title_and_tasks(db, mini_plan):
    _user, plan = mini_plan
    before = plan_to_dict(db, plan)
    push_snapshot(db, plan, source="test")
    plan.title = "Changed"
    leaf = next(t for t in plan.tasks if t.code == "T2.1")
    leaf.title = "Renamed leaf"
    db.flush()

    ok = restore_snapshot(db, plan)
    assert ok is True
    db.commit()
    db.refresh(plan)
    after = plan_to_dict(db, plan)
    assert after["title"] == before["title"]
    by_code = {t["code"]: t for t in after["tasks"]}
    assert by_code["T2.1"]["title"] == "In vitro"


def test_redo_after_undo(db, mini_plan):
    _user, plan = mini_plan
    push_snapshot(db, plan, source="test")
    plan.title = "After edit"
    db.flush()
    assert restore_snapshot(db, plan) is True
    assert plan.title != "After edit"
    assert redo_snapshot(db, plan) is True
    db.commit()
    db.refresh(plan)
    assert plan.title == "After edit"


def test_apply_imported_xlsx_demo(db, mini_plan):
    _user, plan = mini_plan
    content = EXAMPLE_XLSX.read_bytes()
    ok, errors, codes, title = apply_imported_xlsx(
        db, plan, content, source="excel", changed_by="user"
    )
    assert ok is True, errors
    assert not errors
    assert len(codes) > 0
    assert title
    db.commit()
    assert len(plan.tasks) > 0


def test_load_seed_start_is_today(db, mini_plan):
    _user, plan = mini_plan
    load_seed_into_plan(db, plan)
    db.commit()
    db.refresh(plan)
    assert PLAN_START == date.today()
    assert plan.start_date == date.today()
    assert db.query(Task).filter(Task.plan_id == plan.id).count() > 0
