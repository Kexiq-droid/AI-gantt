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

MAX_BATCH_OPS = 3

CLARIFY_OVER_LIMIT = (
    "В запросе больше 3 отдельных действий. Уточните, какие 1–3 выполнить сейчас "
    "(остальные сделаем следующим сообщением)."
)

MASS_DELETE_NEED_CONFIRM = (
    "Массовое удаление требует явного подтверждения пользователя в чате "
    "(«да» / «подтверждаю» после предупреждения). Не применяйте патч без подтверждения."
)


def _is_mass_delete_ops(operations: list[Any]) -> bool:
    """True if ops would wipe many/all tasks — must be confirmed."""
    ops = operations or []
    for op in ops:
        if not isinstance(op, dict):
            continue
        kind = op.get("op") or op.get("type")
        if kind == "clear":
            return True
        if kind == "delete" and (
            op.get("all") is True or (op.get("filter") or {}).get("all") is True
        ):
            return True
    deletes = [
        op
        for op in ops
        if isinstance(op, dict) and (op.get("op") or op.get("type")) == "delete"
    ]
    return len(deletes) >= 2


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
    """If over limit, return clarification payload; else None."""
    n = len(operations or [])
    if n <= MAX_BATCH_OPS:
        return None
    return {
        "ok": False,
        "need_clarification": True,
        "count": n,
        "max": MAX_BATCH_OPS,
        "message": CLARIFY_OVER_LIMIT,
        "operations_preview": operations[:8],
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
        if _is_mass_delete_ops(operations):
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
        limited = ops_limit_result(operations)
        if limited:
            ctx["planned_ops"] = None
            ctx["need_clarification"] = True
            return limited, []
        ctx["planned_ops"] = operations
        ctx["need_clarification"] = False
        return {
            "ok": True,
            "need_clarification": False,
            "count": len(operations),
            "max": MAX_BATCH_OPS,
            "analysis": (args.get("analysis") or "")[:500],
            "operations": operations,
            "next": "Вызови apply_plan_patch с этим же списком operations.",
        }, []

    if name == "apply_plan_patch":
        operations = args.get("operations") or []
        dry_run = bool(args.get("dry_run"))
        confirmed = bool(args.get("confirmed"))
        limited = ops_limit_result(operations)
        if limited:
            ctx["need_clarification"] = True
            return limited, []
        if _is_mass_delete_ops(operations) and not confirmed and not dry_run:
            return {
                "ok": False,
                "need_confirmation": True,
                "errors": [MASS_DELETE_NEED_CONFIRM],
                "message": MASS_DELETE_NEED_CONFIRM,
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
