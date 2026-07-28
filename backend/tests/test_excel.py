from datetime import date
from io import BytesIO

from openpyxl import Workbook

from backend.app.services.excel_io import (
    export_filename,
    export_plan_xlsx,
    import_plan_xlsx,
)
from backend.app.services.validate import validate_plan_dict


def _sample_plan():
    return {
        "title": "Demo R&D",
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


def test_excel_roundtrip():
    plan = _sample_plan()
    raw = export_plan_xlsx(plan)
    imported = import_plan_xlsx(raw, plan_start=date(2026, 3, 2))
    assert not validate_plan_dict(imported)
    codes = {t["code"] for t in imported["tasks"]}
    assert codes == {"P1", "T1.1", "T1.2"}
    t12 = next(t for t in imported["tasks"] if t["code"] == "T1.2")
    assert "T1.1" in t12["predecessors"]
    assert t12["parent"] == "P1"
    assert imported["title"] == "Demo R&D"
    p1 = next(t for t in imported["tasks"] if t["code"] == "P1")
    assert p1["title"] == "Фаза"
    assert p1["parent"] is None


def test_excel_legacy_plain_header_still_imports():
    """Old draft exports (header on row 1) must keep working."""
    wb = Workbook()
    ws = wb.active
    ws.append(["код", "задача", "описание", "исполнитель", "длительность", "предшественники", "родитель"])
    ws.append(["P1", "Фаза", "", "", 5, "", ""])
    ws.append(["T1.1", "Задача", "desc", "Иванов", 3, "", "P1"])
    buf = BytesIO()
    wb.save(buf)
    imported = import_plan_xlsx(buf.getvalue(), plan_start=date(2026, 3, 2))
    assert {t["code"] for t in imported["tasks"]} == {"P1", "T1.1"}


def test_export_filename_sanitizes():
    name = export_filename({"title": 'План: тест/А"B'}, when=date(2026, 7, 28))
    assert name.startswith("BioPlan_")
    assert name.endswith("_2026-07-28.xlsx")
    assert "/" not in name
    assert '"' not in name
