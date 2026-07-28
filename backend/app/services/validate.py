from __future__ import annotations

from typing import Any


def validate_plan_dict(plan: dict[str, Any]) -> list[str]:
    """Validate plan snapshot dict. Returns list of error messages (empty = ok)."""
    errors: list[str] = []
    tasks = plan.get("tasks") or []
    by_code = {t["code"]: t for t in tasks}
    codes = set(by_code)

    if len(codes) != len(tasks):
        errors.append("Коды задач должны быть уникальны в плане")

    for t in tasks:
        parent = t.get("parent")
        if parent:
            if parent not in codes:
                errors.append(f"Задача {t['code']}: родитель {parent} не найден")
            elif parent == t["code"]:
                errors.append(f"Задача {t['code']}: ссылается сама на себя как родитель")

    for t in tasks:
        seen: set[str] = set()
        cur = t.get("parent")
        while cur:
            if cur in seen or cur == t["code"]:
                errors.append(f"Цикл в иерархии у задачи {t['code']}")
                break
            seen.add(cur)
            cur = (by_code.get(cur) or {}).get("parent")

    children: dict[str | None, list[str]] = {}
    for t in tasks:
        children.setdefault(t.get("parent"), []).append(t["code"])

    for t in tasks:
        has_children = bool(children.get(t["code"]))
        if not has_children and int(t.get("duration_days") or 0) <= 0:
            errors.append(f"Задача {t['code']}: длительность должна быть > 0")

    edges: list[tuple[str, str]] = []
    for t in tasks:
        for pred in t.get("predecessors") or []:
            if pred not in codes:
                errors.append(f"Задача {t['code']}: предшественник {pred} не найден")
            else:
                edges.append((pred, t["code"]))

    adj: dict[str, list[str]] = {c: [] for c in codes}
    for a, b in edges:
        adj[a].append(b)

    state: dict[str, int] = {c: 0 for c in codes}

    def dfs(node: str) -> bool:
        state[node] = 1
        for nxt in adj[node]:
            if state[nxt] == 1:
                return True
            if state[nxt] == 0 and dfs(nxt):
                return True
        state[node] = 2
        return False

    for c in codes:
        if state[c] == 0 and dfs(c):
            errors.append("Обнаружен цикл в зависимостях FS")
            break

    return errors
