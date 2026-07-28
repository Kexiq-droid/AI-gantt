from __future__ import annotations

import re
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from backend.app.seed_data import compute_schedule

HEADERS = ["код", "задача", "описание", "исполнитель", "длительность", "предшественники", "родитель"]
HEADER_ALIASES = {
    "код": ("код", "code"),
    "задача": ("задача", "title", "название"),
    "описание": ("описание", "description"),
    "исполнитель": ("исполнитель", "assignee"),
    "длительность": ("длительность", "duration", "duration_days"),
    "предшественники": ("предшественники", "predecessors"),
    "родитель": ("родитель", "parent"),
}

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "bioplan_logo.png"

# Brand colors (match frontend theme)
ACCENT = "0F766E"
PHASE_BG = "E6F7F4"
PHASE_FG = "134E4A"
HEADER_FG = "FFFFFF"
MUTED = "5C6B66"
TEXT = "1C2422"
BORDER = "DDD4C8"

COL_WIDTHS = {
    "A": 12,   # код
    "B": 38,   # задача
    "C": 48,   # описание
    "D": 16,   # исполнитель
    "E": 13,   # длительность
    "F": 20,   # предшественники
    "G": 12,   # родитель
}

HEADER_ROW = 5  # 1-based: logo/title block above


def export_filename(plan: dict[str, Any], when: date | None = None) -> str:
    """Safe download name: BioPlan_<title>_<YYYY-MM-DD>.xlsx"""
    when = when or date.today()
    title = str(plan.get("title") or "plan").strip() or "plan"
    title = re.sub(r'[\\/:*?"<>|]+', "_", title)
    title = re.sub(r"\s+", "_", title).strip("._")[:60] or "plan"
    return f"BioPlan_{title}_{when.isoformat()}.xlsx"


def content_disposition(filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "BioPlan.xlsx"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def export_plan_xlsx(plan: dict[str, Any]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "План"

    thin = Side(style="thin", color=BORDER)
    grid = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor=ACCENT)
    header_font = Font(name="Calibri", bold=True, color=HEADER_FG, size=11)
    phase_fill = PatternFill("solid", fgColor=PHASE_BG)
    phase_font = Font(name="Calibri", bold=True, color=PHASE_FG, size=11)
    body_font = Font(name="Calibri", color=TEXT, size=11)
    title_font = Font(name="Calibri", bold=True, color=ACCENT, size=16)
    meta_font = Font(name="Calibri", color=MUTED, size=10)

    # —— Brand header ——
    ws.merge_cells("C1:G1")
    ws["C1"] = "R&D планирование"
    ws["C1"].font = title_font
    ws["C1"].alignment = Alignment(vertical="center")

    ws.merge_cells("A2:G2")
    ws["A2"] = f"План: {plan.get('title') or 'Без названия'}"
    ws["A2"].font = Font(name="Calibri", bold=True, color=TEXT, size=12)

    ws.merge_cells("A3:G3")
    exported_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    ws["A3"] = f"Экспорт: {exported_at}"
    ws["A3"].font = meta_font

    # Accent strip under brand block
    for col in range(1, 8):
        cell = ws.cell(row=4, column=col, value="")
        cell.fill = PatternFill("solid", fgColor=ACCENT)
    ws.row_dimensions[1].height = 36
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 16
    ws.row_dimensions[4].height = 6

    if LOGO_PATH.is_file():
        logo = XLImage(str(LOGO_PATH))
        logo.width = 150
        logo.height = 44
        ws.add_image(logo, "A1")
    else:
        ws.merge_cells("A1:B1")
        ws["A1"] = "BioPlan"
        ws["A1"].font = title_font
        ws["A1"].alignment = Alignment(vertical="center")

    # —— Table header ——
    for col_idx, name in enumerate(HEADERS, start=1):
        cell = ws.cell(row=HEADER_ROW, column=col_idx, value=name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = grid
    ws.row_dimensions[HEADER_ROW].height = 22

    # —— Data ——
    for i, t in enumerate(plan.get("tasks") or []):
        row = HEADER_ROW + 1 + i
        is_phase = not t.get("parent")
        values = [
            t["code"],
            t["title"],
            t.get("description") or "",
            t.get("assignee") or "",
            t.get("duration_days") or 1,
            ",".join(t.get("predecessors") or []),
            t.get("parent") or "",
        ]
        for col_idx, value in enumerate(values, start=1):
            cell = ws.cell(row=row, column=col_idx, value=value)
            cell.border = grid
            cell.font = phase_font if is_phase else body_font
            if is_phase:
                cell.fill = phase_fill
            wrap = col_idx in (2, 3)
            indent = 0 if is_phase or col_idx != 2 else 1
            cell.alignment = Alignment(
                vertical="center",
                wrap_text=wrap,
                indent=indent,
            )
        # Description rows get a bit more height when long
        desc = str(t.get("description") or "")
        if len(desc) > 60:
            ws.row_dimensions[row].height = 36
        elif is_phase:
            ws.row_dimensions[row].height = 20

    last_data_row = HEADER_ROW + len(plan.get("tasks") or [])
    if last_data_row < HEADER_ROW:
        last_data_row = HEADER_ROW

    for letter, width in COL_WIDTHS.items():
        ws.column_dimensions[letter].width = width

    ws.freeze_panes = f"A{HEADER_ROW + 1}"
    ws.auto_filter.ref = f"A{HEADER_ROW}:{get_column_letter(len(HEADERS))}{max(last_data_row, HEADER_ROW)}"
    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"

    # Soft note for importers (ignored by our importer — no code column)
    note_row = last_data_row + 2
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=7)
    note = ws.cell(
        row=note_row,
        column=1,
        value="Подсказка: при импорте сохраните строку заголовков (код, задача, …). "
        "Строки шапки BioPlan можно оставить — они пропускаются.",
    )
    note.font = Font(name="Calibri", italic=True, color=MUTED, size=9)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _find_header_row(rows: list[tuple[Any, ...]]) -> tuple[int, list[str]]:
    """Locate the table header among brand/meta rows. Returns (index, lowered headers)."""
    for idx, row in enumerate(rows[:30]):
        cells = [str(c or "").strip().lower() for c in row]
        if "код" in cells or "code" in cells:
            if any(h in cells for h in ("задача", "title", "название")):
                return idx, cells
    raise ValueError("Не найдена строка заголовков (ожидаются колонки «код», «задача», …)")


def import_plan_xlsx(content: bytes, plan_start: date | None = None) -> dict[str, Any]:
    wb = load_workbook(BytesIO(content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Пустой Excel")

    header_idx, header = _find_header_row(rows)

    def col(*names: str) -> int:
        for n in names:
            if n in header:
                return header.index(n)
        raise ValueError(f"Нет колонки {names[0]}")

    i_code = col(*HEADER_ALIASES["код"])
    i_title = col(*HEADER_ALIASES["задача"])
    i_desc = col(*HEADER_ALIASES["описание"])
    i_assignee = col(*HEADER_ALIASES["исполнитель"])
    i_dur = col(*HEADER_ALIASES["длительность"])
    i_pred = col(*HEADER_ALIASES["предшественники"])
    i_parent = col(*HEADER_ALIASES["родитель"])

    # Prefer title from brand header if present
    plan_title = "Импортированный план"
    for row in rows[:header_idx]:
        for cell in row:
            text = str(cell or "").strip()
            if text.lower().startswith("план:"):
                plan_title = text.split(":", 1)[1].strip() or plan_title
                break

    def cell(row: tuple[Any, ...], index: int) -> Any:
        return row[index] if index < len(row) else None

    tasks: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        code = str(cell(row, i_code) or "").strip()
        if not code:
            continue
        # Skip footer hints / non-data rows
        if " " in code and not re.match(r"^[PT]\d", code, re.I):
            continue

        preds_raw = str(cell(row, i_pred) or "").strip()
        preds = [p.strip() for p in preds_raw.replace(";", ",").split(",") if p.strip()]
        parent = str(cell(row, i_parent) or "").strip() or None
        title_raw = str(cell(row, i_title) or code)
        tasks.append(
            {
                "code": code,
                "title": title_raw.strip(),
                "description": str(cell(row, i_desc) or "").strip(),
                "assignee": str(cell(row, i_assignee) or "").strip(),
                "duration_days": int(cell(row, i_dur) or 1),
                "predecessors": preds,
                "parent": parent,
                "sort_order": idx * 10,
                "last_changed_by": "user",
            }
        )

    if not tasks:
        raise ValueError("В файле нет задач для импорта")

    start = plan_start or date.today()
    starts = compute_schedule(tasks, start)
    for t in tasks:
        t["start_date"] = starts[t["code"]].isoformat()

    return {
        "title": plan_title,
        "start_date": start.isoformat(),
        "tasks": tasks,
    }
