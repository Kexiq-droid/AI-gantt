from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Any

from backend.app.seed_data import compute_schedule
from backend.app.services.validate import validate_plan_dict


def _op_kind(op: dict[str, Any]) -> str:
    return str(op.get("op") or op.get("type") or "").strip().lower()


def _should_reschedule(ops: list[Any]) -> bool:
    """Recompute FS dates after graph/duration changes (not after pure shift/reassign)."""
    for op in ops or []:
        if not isinstance(op, dict):
            continue
        kind = _op_kind(op)
        if kind in ("create", "set_deps", "set_dependencies", "delete", "clear"):
            return True
        if kind == "update":
            fields = dict(op.get("fields") or {})
            if "duration_days" in op or "duration_days" in fields or "predecessors" in fields:
                return True
    return False


def reschedule_plan_dict(plan: dict[str, Any]) -> dict[str, Any]:
    """Set task start_date from predecessors (finish-to-start cascade)."""
    tasks = plan.get("tasks") or []
    if not tasks:
        return plan
    plan_start = date.fromisoformat(
        plan.get("start_date") or date.today().isoformat()
    )
    starts = compute_schedule(tasks, plan_start)
    for t in tasks:
        code = t.get("code")
        if code in starts:
            t["start_date"] = starts[code].isoformat()
    return plan


def _matches_filter(task: dict[str, Any], filt: dict[str, Any] | None, by_code: dict) -> bool:
    if not filt:
        return True
    if filt.get("all") is True:
        return True
    # LLM often sends {"code":"T2.1"} instead of {"codes":["T2.1"]}
    if "code" in filt and "codes" not in filt:
        return task["code"] == str(filt["code"])
    if "codes" in filt:
        codes = filt["codes"]
        if isinstance(codes, str):
            codes = [codes]
        return task["code"] in set(codes)
    if "phase_code" in filt:
        phase = filt["phase_code"]
        if task["code"] == phase:
            return True
        # descendant of phase
        cur = task.get("parent")
        while cur:
            if cur == phase:
                return True
            cur = (by_code.get(cur) or {}).get("parent")
        return False
    if "assignee" in filt:
        return (task.get("assignee") or "") == filt["assignee"]
    return False


def apply_plan_patch_dict(
    plan: dict[str, Any], patch: dict[str, Any], changed_by: str = "agent"
) -> tuple[dict[str, Any], list[str], list[str]]:
    """
    Apply patch to plan dict (pure). Returns (new_plan, changes_codes, errors).
    Does not mutate input on failure.
    """
    working = deepcopy(plan)
    tasks = working.setdefault("tasks", [])
    by_code = {t["code"]: t for t in tasks}
    changes: set[str] = set()
    ops = patch.get("operations") or []

    try:
        for op in ops:
            # Normalize common LLM aliases
            if "op" not in op and "type" in op:
                op = {**op, "op": op["type"]}
            if "days" not in op and "by_days" in op:
                op = {**op, "days": op["by_days"]}
            if "days" not in op and "shift_days" in op:
                op = {**op, "days": op["shift_days"]}
            kind = op.get("op")
            if kind == "shift":
                days = int(op.get("days") or 0)
                filt = op.get("filter")
                for t in tasks:
                    if _matches_filter(t, filt, by_code):
                        start = date.fromisoformat(t["start_date"])
                        t["start_date"] = (start + timedelta(days=days)).isoformat()
                        t["last_changed_by"] = changed_by
                        changes.add(t["code"])
            elif kind == "reassign":
                assignee = op.get("assignee") or ""
                filt = op.get("filter")
                for t in tasks:
                    if _matches_filter(t, filt, by_code):
                        t["assignee"] = assignee
                        t["last_changed_by"] = changed_by
                        changes.add(t["code"])
            elif kind == "create":
                code = op["code"]
                if code in by_code:
                    raise ValueError(f"Код {code} уже существует")
                sort_order = op.get("sort_order")
                after = op.get("after") or op.get("insert_after") or op.get("sort_after")
                position = str(op.get("position") or "").strip().lower()
                if sort_order is None and after:
                    anchor = by_code.get(str(after))
                    if not anchor:
                        raise ValueError(f"create {code}: after={after} не найден в плане")
                    sort_order = int(anchor.get("sort_order") or 0) + 1
                    for t in tasks:
                        if int(t.get("sort_order") or 0) >= sort_order:
                            t["sort_order"] = int(t.get("sort_order") or 0) + 1
                elif sort_order is None and position in ("start", "начало"):
                    min_so = min((int(t.get("sort_order") or 0) for t in tasks), default=1)
                    sort_order = min_so - 1
                elif sort_order is None:
                    # position end / default — в конец
                    sort_order = max((int(t.get("sort_order") or 0) for t in tasks), default=0) + 1
                row = {
                    "code": code,
                    "parent": op.get("parent"),
                    "title": op.get("title") or code,
                    "description": op.get("description") or "",
                    "assignee": op.get("assignee") or "",
                    "duration_days": int(op.get("duration_days") or 1),
                    "start_date": op.get("start_date")
                    or working.get("start_date")
                    or date.today().isoformat(),
                    "sort_order": int(sort_order),
                    "progress_pct": max(0, min(100, int(op.get("progress_pct") or 0))),
                    "last_changed_by": changed_by,
                    "predecessors": list(op.get("predecessors") or []),
                }
                tasks.append(row)
                by_code[code] = row
                changes.add(code)
            elif kind == "update":
                code = op["code"]
                if code not in by_code:
                    raise ValueError(f"Задача {code} не найдена")
                # Accept both {"fields": {...}} and flat keys on the op itself
                # (LLM often sends duration_days / title at the top level).
                fields = dict(op.get("fields") or {})
                for key in (
                    "title",
                    "description",
                    "assignee",
                    "duration_days",
                    "start_date",
                    "parent",
                    "sort_order",
                    "progress_pct",
                ):
                    if key in op and key not in fields:
                        fields[key] = op[key]
                if not fields:
                    raise ValueError(
                        f"update для {code}: нет полей (ожидается fields или duration_days/title/...)"
                    )
                t = by_code[code]
                changed_any = False
                for key in (
                    "title",
                    "description",
                    "assignee",
                    "duration_days",
                    "start_date",
                    "parent",
                    "sort_order",
                    "progress_pct",
                ):
                    if key in fields:
                        val = fields[key]
                        if key in ("duration_days", "sort_order", "progress_pct"):
                            val = int(val)
                        if key == "progress_pct":
                            val = max(0, min(100, val))
                            if any(x.get("parent") == code for x in tasks):
                                raise ValueError(
                                    f"Прогресс фазы {code} считается автоматически по дочерним"
                                )
                        if t.get(key) != val:
                            changed_any = True
                        t[key] = val
                t["last_changed_by"] = changed_by
                if changed_any:
                    changes.add(code)
            elif kind in ("swap", "swap_order", "swap_places"):
                codes = op.get("codes")
                if isinstance(codes, str):
                    codes = [codes]
                if not codes or len(codes) != 2:
                    a = op.get("a") or op.get("code_a") or op.get("left")
                    b = op.get("b") or op.get("code_b") or op.get("right")
                    codes = [a, b]
                if len(codes) != 2 or not codes[0] or not codes[1]:
                    raise ValueError('swap: нужны два кода, например {"op":"swap","codes":["P3","P4"]}')
                ca, cb = str(codes[0]), str(codes[1])
                if ca == cb:
                    raise ValueError("swap: коды должны различаться")
                if ca not in by_code or cb not in by_code:
                    missing = [c for c in (ca, cb) if c not in by_code]
                    raise ValueError(f"swap: не найдены задачи {', '.join(missing)}")

                def subtree_codes(root: str) -> list[str]:
                    out = [root]
                    i = 0
                    while i < len(out):
                        cur = out[i]
                        i += 1
                        for t in tasks:
                            if t.get("parent") == cur:
                                out.append(t["code"])
                    return out

                ta, tb = by_code[ca], by_code[cb]
                ta["sort_order"], tb["sort_order"] = int(tb["sort_order"]), int(ta["sort_order"])
                start_a = date.fromisoformat(ta["start_date"])
                start_b = date.fromisoformat(tb["start_date"])
                delta_a = start_b - start_a  # move A subtree onto B's timeline slot
                delta_b = start_a - start_b
                for code in subtree_codes(ca):
                    t = by_code[code]
                    t["start_date"] = (date.fromisoformat(t["start_date"]) + delta_a).isoformat()
                    t["last_changed_by"] = changed_by
                    changes.add(code)
                for code in subtree_codes(cb):
                    t = by_code[code]
                    t["start_date"] = (date.fromisoformat(t["start_date"]) + delta_b).isoformat()
                    t["last_changed_by"] = changed_by
                    changes.add(code)
            elif kind in ("set_deps", "set_dependencies"):
                code = op["code"]
                if code not in by_code:
                    raise ValueError(f"Задача {code} не найдена")
                preds = op.get("predecessors")
                if preds is None and "fields" in op:
                    preds = (op.get("fields") or {}).get("predecessors")
                by_code[code]["predecessors"] = list(preds or [])
                by_code[code]["last_changed_by"] = changed_by
                changes.add(code)
            elif kind == "delete":
                filt = op.get("filter") or {}
                if filt.get("all") is True or op.get("all") is True:
                    removed = [t["code"] for t in tasks]
                    tasks.clear()
                    by_code.clear()
                    changes.update(removed)
                    continue
                code = op.get("code")
                if not code:
                    raise ValueError("delete: укажите code или filter.all=true")
                if code not in by_code:
                    raise ValueError(f"Задача {code} не найдена")
                # remove task and deps pointing to it; also children? require explicit
                children = [t["code"] for t in tasks if t.get("parent") == code]
                if children:
                    raise ValueError(f"Нельзя удалить {code}: есть дочерние {', '.join(children)}")
                tasks[:] = [t for t in tasks if t["code"] != code]
                for t in tasks:
                    t["predecessors"] = [p for p in (t.get("predecessors") or []) if p != code]
                by_code = {t["code"]: t for t in tasks}
                changes.add(code)
            elif kind == "clear":
                # alias: clear whole plan
                removed = [t["code"] for t in tasks]
                tasks.clear()
                by_code.clear()
                changes.update(removed)
            elif kind in ("set_title", "rename_plan"):
                title = (op.get("title") or "").strip()
                if not title:
                    raise ValueError("set_title: укажите непустой title")
                title = title[:200]
                if working.get("title") != title:
                    working["title"] = title
                    changes.add("__title__")
            else:
                raise ValueError(f"Неизвестная операция: {kind}")
    except Exception as exc:  # noqa: BLE001
        return plan, [], [str(exc)]

    errors = validate_plan_dict(working)
    if errors:
        return plan, [], errors
    # Mutating ops that matched nothing are failures (prevents LLM "done" lies)
    mutating = any(
        (op.get("op") or op.get("type"))
        in {
            "shift",
            "reassign",
            "update",
            "delete",
            "clear",
            "set_deps",
            "set_dependencies",
            "create",
            "swap",
            "swap_order",
            "swap_places",
            "set_title",
            "rename_plan",
        }
        for op in ops
    )
    if mutating and not changes:
        return plan, [], [
            "Патч не изменил ни одной задачи. Для одной задачи используй "
            'filter.all=true — весь план; filter.code / filter.codes; '
            'для фазы — filter.phase_code.'
        ]
    if _should_reschedule(ops):
        reschedule_plan_dict(working)
    return working, sorted(changes), []
