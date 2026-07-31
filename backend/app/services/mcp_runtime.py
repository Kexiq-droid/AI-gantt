"""Shared MCP tool surface for web agent (in-process) and Cursor (stdio).

Chat and IDE call the same execute_tool() contract; transport differs.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models import AgentJob, Plan
from backend.app.services.patch import apply_plan_patch_dict
from backend.app.services.plan_store import (
    apply_imported_xlsx,
    plan_to_dict,
    push_snapshot,
    restore_snapshot,
    _replace_plan_content,
)
from backend.app.services.validate import validate_plan_dict

# Один лимит на apply — агент должен отдавать весь план целиком, без «по 3».
MAX_BATCH_OPS = 60
MAX_PLAN_BUILD_OPS = MAX_BATCH_OPS
_PLAN_BUILD_KINDS = frozenset({"create", "set_deps", "update"})

CLARIFY_OVER_LIMIT = (
    f"Слишком много операций за один раз (больше {MAX_BATCH_OPS}). "
    "Сократи WBS или разбей на два логических этапа (например, фазы 1–4, затем 5–7), "
    "но каждый этап применяй целиком с листовыми задачами — не по одной задаче."
)

MASS_DELETE_NEED_CONFIRM = (
    "Массовое удаление требует явного подтверждения пользователя в чате "
    "(«да» / «подтверждаю» после предупреждения). Не применяйте патч без подтверждения."
)

CLARIFY_CREATE_PLACEMENT = (
    "Не хватает данных, куда вставить новую задачу. НЕ применяй патч. "
    "Спроси пользователя коротко: "
    "(1) parent / фаза, "
    "(2) позиция среди siblings — after=код или position=end, "
    "(3) predecessors по технологии работ (или [] если можно параллельно). "
    "Исключения: полный план с нуля; пользователь уже указал эти поля; "
    "«как считаешь нужным» / «создавай всё»."
)

CLARIFY_CASCADE = (
    "План собран без каскада: у листовых задач нет технологических зависимостей. "
    "НЕ применяй патч. Пересобери WBS: критический путь последовательно (predecessors), "
    "независимые работы — параллельно (общий predecessor или []). "
    "В ответе пользователю кратко укажи, что идёт последовательно, а что параллельно."
)

REPLACE_PLAN_NEED_CONFIRM = (
    "В плане уже есть задачи, а operations содержат очистку + новый WBS. "
    "НЕ применяй патч. Спроси: «Заменю текущий план целиком? Напишите да / нет.» "
    "После «да» — тот же список operations в plan_commands и apply_plan_patch с confirmed=true."
)


def _op_kind(op: Any) -> str:
    if not isinstance(op, dict):
        return ""
    return str(op.get("op") or op.get("type") or "").strip().lower()


def _is_mass_delete_ops(operations: list[Any]) -> bool:
    """True if ops would wipe many/all tasks — must be confirmed."""
    ops = operations or []
    for op in ops:
        if not isinstance(op, dict):
            continue
        kind = _op_kind(op)
        if kind == "clear":
            return True
        if kind == "delete" and (
            op.get("all") is True or (op.get("filter") or {}).get("all") is True
        ):
            return True
    deletes = [op for op in ops if _op_kind(op) == "delete"]
    return len(deletes) >= 2


def _is_plan_build_ops(operations: list[Any]) -> bool:
    """Multi-create WBS build — large batch + cascade rules (not a single ad-hoc create)."""
    ops = [op for op in (operations or []) if isinstance(op, dict)]
    # Allow leading mass-delete when replacing a plan in one batch.
    ops = [op for op in ops if not (_op_kind(op) == "delete" and _is_mass_delete_ops([op]))]
    if not ops:
        return False
    kinds = {_op_kind(op) for op in ops}
    if not (kinds and kinds <= _PLAN_BUILD_KINDS and "create" in kinds):
        return False
    creates = [op for op in ops if _op_kind(op) == "create"]
    phases = [
        op
        for op in creates
        if not op.get("parent") and _is_phase_code(op.get("code"))
    ]
    leaves = [op for op in creates if op.get("parent")]
    # Целый план или заметный кусок WBS; одиночный create — не build.
    return len(creates) >= 3 or (bool(phases) and bool(leaves))


def _is_phase_code(code: Any) -> bool:
    s = str(code or "").strip()
    return bool(s) and s[0] in "Pp" and s[1:].isdigit()


def _create_has_parent(op: dict[str, Any]) -> bool:
    if "parent" not in op:
        return False
    parent = op.get("parent")
    if parent is None or parent == "":
        # Top-level phase only.
        return _is_phase_code(op.get("code"))
    return True


def _create_has_position(op: dict[str, Any]) -> bool:
    if op.get("after") or op.get("insert_after") or op.get("sort_after"):
        return True
    if "sort_order" in op:
        return True
    pos = str(op.get("position") or "").strip().lower()
    return pos in ("end", "start", "конец", "начало")


def _create_has_deps_field(op: dict[str, Any]) -> bool:
    return "predecessors" in op


def create_placement_issues(operations: list[Any]) -> list[dict[str, Any]]:
    """Ad-hoc create ops missing parent / position / predecessors."""
    issues: list[dict[str, Any]] = []
    for op in operations or []:
        if not isinstance(op, dict) or _op_kind(op) != "create":
            continue
        missing: list[str] = []
        if not _create_has_parent(op):
            missing.append("parent")
        if not _create_has_position(op):
            missing.append("position|after")
        if not _create_has_deps_field(op):
            missing.append("predecessors")
        if missing:
            issues.append({"code": op.get("code"), "title": op.get("title"), "missing": missing})
    return issues


def plan_build_cascade_issues(operations: list[Any]) -> list[str]:
    """Require real WBS: leaf tasks + technological deps (not phases-only)."""
    creates = [
        op for op in (operations or []) if isinstance(op, dict) and _op_kind(op) == "create"
    ]
    leaves = [op for op in creates if op.get("parent")]
    phases = [
        op
        for op in creates
        if not op.get("parent") and _is_phase_code(op.get("code"))
    ]
    if len(phases) >= 2 and len(leaves) == 0:
        return [
            "Нельзя создавать только фазы без листовых задач. "
            "В том же списке operations добавь задачи T* с duration_days и predecessors, "
            "затем один apply_plan_patch на весь WBS. Не дроби и не спрашивай пользователя."
        ]
    if len(leaves) < 2:
        return []
    with_deps = [op for op in leaves if list(op.get("predecessors") or [])]
    if not with_deps:
        return [
            "У листовых задач нет predecessors — нужен каскад по технологии работ "
            "(последовательные зависимости; параллельно только независимые работы)."
        ]
    return []


def create_ops_gate_result(operations: list[Any]) -> dict[str, Any] | None:
    """Block incomplete ad-hoc creates or non-cascading plan builds."""
    ops = [op for op in (operations or []) if isinstance(op, dict)]
    if not any(_op_kind(op) == "create" for op in ops):
        return None

    # Replace batch: delete-all + creates — treat as plan build after delete.
    non_delete = [op for op in ops if _op_kind(op) != "delete"]
    build = _is_plan_build_ops(ops) or (
        _is_plan_build_ops(non_delete) and _is_mass_delete_ops(ops)
    )

    if build:
        cascade = plan_build_cascade_issues(non_delete if non_delete else ops)
        if cascade:
            return {
                "ok": False,
                "need_clarification": True,
                "need_chunking": False,
                "reason": "cascade",
                "message": CLARIFY_CASCADE,
                "errors": cascade,
                "operations_preview": ops[:8],
            }
        return None

    issues = create_placement_issues(ops)
    if not issues:
        return None
    return {
        "ok": False,
        "need_clarification": True,
        "need_chunking": False,
        "reason": "create_placement",
        "message": CLARIFY_CREATE_PLACEMENT,
        "issues": issues,
        "operations_preview": ops[:8],
    }


# Exported over MCP stdio (Cursor). Chat may also use chat-only tools below.
MCP_PUBLIC_TOOLS = frozenset(
    {
        "get_plan_snapshot",
        "validate_plan",
        "apply_plan_patch",
        "undo_plan",
        "list_overloaded_assignees",
    }
)


def ops_limit_result(operations: list[Any]) -> dict[str, Any] | None:
    """If over hard cap, return error payload; else None (allow full list)."""
    ops = list(operations or [])
    n = len(ops)
    if n <= MAX_BATCH_OPS:
        return None
    return {
        "ok": False,
        "need_clarification": True,
        "need_chunking": False,
        "count": n,
        "max": MAX_BATCH_OPS,
        "message": CLARIFY_OVER_LIMIT,
        "operations_preview": ops[:8],
    }


def _import_job_attachment(db: Session, plan: Plan, job: AgentJob) -> tuple[Any, list[str]]:
    path = (job.attachment_path or "").strip()
    if not path:
        return {
            "ok": False,
            "errors": ["К сообщению не прикреплён Excel. Попросите пользователя приложить .xlsx."],
        }, []
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "errors": [f"Файл вложения не найден: {job.attachment_name or path}"]}, []
    content = p.read_bytes()
    ok, errors, codes, title = apply_imported_xlsx(
        db, plan, content, source="chat", changed_by="agent"
    )
    if not ok:
        return {"ok": False, "errors": errors, "changes": []}, []
    return {
        "ok": True,
        "errors": [],
        "changes": codes,
        "title": title,
        "filename": job.attachment_name,
        "task_count": len(codes),
    }, codes


def _list_overloaded(db: Session, plan: Plan, *, top_n: int = 5) -> dict[str, Any]:
    snap = plan_to_dict(db, plan)
    tasks = snap.get("tasks") or []
    codes = {t["code"] for t in tasks}
    parents = {t["code"] for t in tasks if any(x.get("parent") == t["code"] for x in tasks)}
    leaves = [t for t in tasks if t["code"] not in parents]
    counts: Counter[str] = Counter()
    for t in leaves:
        name = (t.get("assignee") or "").strip() or "(без исполнителя)"
        counts[name] += 1
    ranked = [
        {"assignee": a, "leaf_tasks": n}
        for a, n in counts.most_common(max(1, min(top_n, 20)))
    ]
    return {
        "ok": True,
        "total_leaf_tasks": len(leaves),
        "total_tasks": len(codes),
        "top": ranked,
    }


def execute_tool(
    db: Session,
    plan: Plan,
    name: str,
    args: dict[str, Any],
    *,
    job: AgentJob | None = None,
    ctx: dict[str, Any] | None = None,
) -> tuple[Any, list[str]]:
    """Execute MCP tool against DB. Returns (result, changed_codes)."""
    ctx = ctx if ctx is not None else {}
    args = args or {}

    if name == "get_plan_snapshot":
        return plan_to_dict(db, plan), []

    if name == "validate_plan":
        snap = args.get("plan") or plan_to_dict(db, plan)
        errs = validate_plan_dict(snap)
        return {"ok": not errs, "errors": errs}, []

    if name == "plan_commands":
        operations = args.get("operations") or []
        if not isinstance(operations, list):
            return {"ok": False, "errors": ["operations must be an array"]}, []
        confirmed = bool(args.get("confirmed"))
        has_creates = any(
            isinstance(op, dict) and _op_kind(op) == "create" for op in operations
        )
        if _is_mass_delete_ops(operations):
            if has_creates:
                # План уже пуст (очистили на «да») — не требуем повторного confirm.
                current_n = len((plan_to_dict(db, plan).get("tasks") or []))
                if not confirmed and current_n > 0:
                    ctx["planned_ops"] = None
                    ctx["need_clarification"] = True
                    return {
                        "ok": False,
                        "need_confirmation": True,
                        "replace_plan": True,
                        "count": len(operations),
                        "message": REPLACE_PLAN_NEED_CONFIRM,
                        "operations_preview": operations[:8],
                    }, []
                # confirmed or empty plan: fall through to gates / limit
            else:
                ctx["planned_ops"] = None
                ctx["need_clarification"] = True
                return {
                    "ok": False,
                    "need_confirmation": True,
                    "count": len(operations),
                    "message": (
                        "Массовое удаление: не применяй патч. Ответь пользователю "
                        "предупреждением и попроси «да»/«нет». После «да» — одна операция "
                        'delete filter.all=true с confirmed=true.'
                    ),
                    "operations_preview": operations[:8],
                }, []
        gated = create_ops_gate_result(operations)
        if gated:
            ctx["planned_ops"] = None
            ctx["need_clarification"] = True
            ctx["need_chunking"] = False
            return gated, []
        limited = ops_limit_result(operations)
        if limited:
            ctx["planned_ops"] = None
            ctx["need_clarification"] = bool(limited.get("need_clarification"))
            ctx["need_chunking"] = bool(limited.get("need_chunking"))
            return limited, []
        ctx["planned_ops"] = operations
        ctx["need_clarification"] = False
        ctx["need_chunking"] = False
        build = _is_plan_build_ops(operations)
        return {
            "ok": True,
            "need_clarification": False,
            "need_chunking": False,
            "count": len(operations),
            "max": MAX_PLAN_BUILD_OPS if build else MAX_BATCH_OPS,
            "plan_build": build,
            "analysis": (args.get("analysis") or "")[:500],
            "operations": operations,
            "next": "Вызови apply_plan_patch с этим же списком operations (весь список).",
        }, []

    if name == "apply_plan_patch":
        operations = args.get("operations") or []
        dry_run = bool(args.get("dry_run"))
        confirmed = bool(args.get("confirmed"))
        gated = create_ops_gate_result(operations)
        if gated:
            ctx["need_clarification"] = True
            ctx["need_chunking"] = False
            return gated, []
        limited = ops_limit_result(operations)
        if limited:
            ctx["need_clarification"] = bool(limited.get("need_clarification"))
            ctx["need_chunking"] = bool(limited.get("need_chunking"))
            return limited, []
        if _is_mass_delete_ops(operations) and not confirmed and not dry_run:
            has_creates = any(
                isinstance(op, dict) and _op_kind(op) == "create" for op in operations
            )
            current_n = len((plan_to_dict(db, plan).get("tasks") or []))
            # delete+WBS на уже пустом плане — просто сборка, не «замена»
            if has_creates and current_n == 0:
                pass
            else:
                msg = REPLACE_PLAN_NEED_CONFIRM if has_creates else MASS_DELETE_NEED_CONFIRM
                return {
                    "ok": False,
                    "need_confirmation": True,
                    "replace_plan": has_creates,
                    "errors": [msg],
                    "message": msg,
                }, []
        if ctx.get("require_plan") and ctx.get("planned_ops") is None and not dry_run:
            return {
                "ok": False,
                "errors": [
                    "Сначала вызови plan_commands с полным списком операций, затем apply_plan_patch."
                ],
            }, []
        current = plan_to_dict(db, plan)
        new_plan, changes, errors = apply_plan_patch_dict(
            current, {"operations": operations}, changed_by="agent"
        )
        if errors:
            return {"ok": False, "errors": errors, "changes": [], "dry_run": dry_run}, []
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "errors": [],
                "changes": changes,
                "message": "Превью: план не изменён. Вызови apply_plan_patch без dry_run для записи.",
            }, []
        push_snapshot(db, plan, source="agent")
        _replace_plan_content(db, plan, new_plan, changed_by="agent")
        db.flush()
        from backend.app.services.assignees import sync_assignees_from_tasks

        sync_assignees_from_tasks(db, plan)
        ctx["applied"] = True
        return {"ok": True, "dry_run": False, "errors": [], "changes": changes}, changes

    if name == "undo_plan":
        ok = restore_snapshot(db, plan)
        db.flush()
        if ok:
            return {"ok": True, "message": "Вернул предыдущее состояние плана."}, []
        return {"ok": False, "errors": ["Стек возврата пуст"], "message": "Нечего возвращать."}, []

    if name == "undo_ui_action":
        from backend.app.services.ui_actions import (
            find_ui_action,
            latest_ui_action,
            mark_ui_action_undone,
        )

        action_id = str(args.get("action_id") or "").strip()
        found = (
            find_ui_action(db, plan.id, action_id)
            if action_id
            else latest_ui_action(db, plan.id)
        )
        if not found:
            return {
                "ok": False,
                "errors": ["UI-действие не найдено"],
                "message": "Не нашёл указанное действие пользователя в UI.",
            }, []
        message, payload = found
        if payload.get("undone"):
            return {
                "ok": False,
                "errors": ["Уже отменено"],
                "message": f"Действие {payload.get('id')} уже было отменено.",
            }, []
        ops = (payload.get("inverse") or {}).get("operations") or []
        if not ops:
            return {
                "ok": False,
                "errors": ["Нет inverse.operations"],
                "message": (
                    f"У действия {payload.get('id')} ({payload.get('kind')}) нет "
                    "точечной отмены. Используй undo_plan для стека snapshot."
                ),
            }, []
        snap = plan_to_dict(db, plan)
        new_plan, changes, errors = apply_plan_patch_dict(
            snap, {"operations": ops}, changed_by="agent"
        )
        if errors:
            return {"ok": False, "errors": errors, "message": "; ".join(errors)}, []
        push_snapshot(db, plan, source="agent")
        _replace_plan_content(db, plan, new_plan, changed_by="agent")
        db.flush()
        from backend.app.services.assignees import sync_assignees_from_tasks

        sync_assignees_from_tasks(db, plan)
        mark_ui_action_undone(db, message, payload)
        db.flush()
        summary = payload.get("summary") or payload.get("id")
        return {
            "ok": True,
            "action_id": payload.get("id"),
            "changes": changes,
            "message": f"Отменил действие UI «{summary}».",
        }, changes

    if name == "list_overloaded_assignees":
        top_n = int(args.get("top_n") or 5)
        return _list_overloaded(db, plan, top_n=top_n), []

    if name == "import_excel_attachment":
        if not job:
            return {"ok": False, "errors": ["Нет контекста job для импорта"]}, []
        return _import_job_attachment(db, plan, job)

    return {"ok": False, "errors": [f"Unknown tool {name}"]}, []
