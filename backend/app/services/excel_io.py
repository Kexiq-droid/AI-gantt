from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook

from backend.app.seed_data import compute_schedule

HEADERS = ["код", "задача", "описание", "исполнитель", "длительность", "предшественники", "родитель"]


def export_plan_xlsx(plan: dict[str, Any]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "План"
    ws.append(HEADERS)
    for t in plan.get("tasks") or []:
        ws.append(
            [
                t["code"],
                t["title"],
                t.get("description") or "",
                t.get("assignee") or "",
                t.get("duration_days") or 1,
                ",".join(t.get("predecessors") or []),
                t.get("parent") or "",
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def import_plan_xlsx(content: bytes, plan_start: date | None = None) -> dict[str, Any]:
    wb = load_workbook(BytesIO(content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Пустой Excel")
    header = [str(c or "").strip().lower() for c in rows[0]]

    def col(*names: str) -> int:
        for n in names:
            if n in header:
                return header.index(n)
        raise ValueError(f"Нет колонки {names[0]}")

    i_code = col("код", "code")
    i_title = col("задача", "title", "название")
    i_desc = col("описание", "description")
    i_assignee = col("исполнитель", "assignee")
    i_dur = col("длительность", "duration", "duration_days")
    i_pred = col("предшественники", "predecessors")
    i_parent = col("родитель", "parent")

    tasks: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[1:], start=2):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        code = str(row[i_code] or "").strip()
        if not code:
            raise ValueError(f"Строка {idx}: пустой код")
        preds_raw = str(row[i_pred] or "").strip()
        preds = [p.strip() for p in preds_raw.replace(";", ",").split(",") if p.strip()]
        parent = str(row[i_parent] or "").strip() or None
        tasks.append(
            {
                "code": code,
                "title": str(row[i_title] or code).strip(),
                "description": str(row[i_desc] or "").strip(),
                "assignee": str(row[i_assignee] or "").strip(),
                "duration_days": int(row[i_dur] or 1),
                "predecessors": preds,
                "parent": parent,
                "sort_order": idx * 10,
                "last_changed_by": "user",
            }
        )

    start = plan_start or date.today()
    starts = compute_schedule(tasks, start)
    for t in tasks:
        t["start_date"] = starts[t["code"]].isoformat()

    return {
        "title": "Импортированный план",
        "start_date": start.isoformat(),
        "tasks": tasks,
    }
