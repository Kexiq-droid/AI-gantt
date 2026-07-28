from datetime import date

from backend.app.services.excel_io import export_plan_xlsx, import_plan_xlsx
from backend.app.services.validate import validate_plan_dict


def test_excel_roundtrip():
    plan = {
        "title": "Demo",
        "start_date": "2026-03-02",
        "tasks": [
            {
                "code": "P1",
                "parent": None,
                "title": "Фаза",
                "description": "d",
                "assignee": "",
                "duration_days": 5,
                "start_date": "2026-03-02",
                "sort_order": 1,
                "predecessors": [],
            },
            {
                "code": "T1.1",
                "parent": "P1",
                "title": "Задача",
                "description": "desc",
                "assignee": "Иванов",
                "duration_days": 3,
                "start_date": "2026-03-02",
                "sort_order": 2,
                "predecessors": [],
            },
            {
                "code": "T1.2",
                "parent": "P1",
                "title": "После",
                "description": "",
                "assignee": "Петрова",
                "duration_days": 2,
                "start_date": "2026-03-05",
                "sort_order": 3,
                "predecessors": ["T1.1"],
            },
        ],
    }
    raw = export_plan_xlsx(plan)
    imported = import_plan_xlsx(raw, plan_start=date(2026, 3, 2))
    assert not validate_plan_dict(imported)
    codes = {t["code"] for t in imported["tasks"]}
    assert codes == {"P1", "T1.1", "T1.2"}
    t12 = next(t for t in imported["tasks"] if t["code"] == "T1.2")
    assert "T1.1" in t12["predecessors"]
    assert t12["parent"] == "P1"
