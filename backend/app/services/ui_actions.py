"""Log human UI plan mutations for the agent (hidden from chat UI)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import ChatMessage, Plan


def new_action_id() -> str:
    return uuid.uuid4().hex[:12]


def log_ui_action(
    db: Session,
    plan: Plan,
    *,
    kind: str,
    summary: str,
    changes: list[str],
    forward: dict[str, Any] | None = None,
    inverse_ops: list[dict[str, Any]] | None = None,
) -> str:
    """Persist a hidden user message the agent can read; not shown in chat UI."""
    action_id = new_action_id()
    payload: dict[str, Any] = {
        "type": "ui_action",
        "id": action_id,
        "kind": kind,
        "summary": summary,
        "changes": list(changes),
        "forward": forward or {},
        "inverse": {"operations": list(inverse_ops or [])},
        "undone": False,
    }
    content = "[UI_ACTION] " + json.dumps(payload, ensure_ascii=False, default=str)
    meta = {
        "hidden": True,
        "source": "ui",
        "action_id": action_id,
        "kind": kind,
        "undone": False,
    }
    db.add(
        ChatMessage(
            plan_id=plan.id,
            role="user",
            content=content,
            meta_json=json.dumps(meta, ensure_ascii=False),
        )
    )
    return action_id


def _parse_meta(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _parse_action_payload(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text.startswith("[UI_ACTION]"):
        return None
    raw = text[len("[UI_ACTION]") :].strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def find_ui_action(
    db: Session, plan_id: int, action_id: str
) -> tuple[ChatMessage, dict[str, Any]] | None:
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.plan_id == plan_id)
        .order_by(ChatMessage.id.desc())
        .limit(200)
    ).all()
    needle = (action_id or "").strip().lower()
    for m in rows:
        meta = _parse_meta(m.meta_json)
        if meta.get("source") != "ui":
            continue
        aid = str(meta.get("action_id") or "").lower()
        payload = _parse_action_payload(m.content or "")
        if not payload:
            continue
        if aid == needle or str(payload.get("id") or "").lower() == needle:
            return m, payload
    return None


def latest_ui_action(
    db: Session, plan_id: int, *, include_undone: bool = False
) -> tuple[ChatMessage, dict[str, Any]] | None:
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.plan_id == plan_id)
        .order_by(ChatMessage.id.desc())
        .limit(100)
    ).all()
    for m in rows:
        meta = _parse_meta(m.meta_json)
        if meta.get("source") != "ui":
            continue
        payload = _parse_action_payload(m.content or "")
        if not payload:
            continue
        if not include_undone and (payload.get("undone") or meta.get("undone")):
            continue
        return m, payload
    return None


def mark_ui_action_undone(db: Session, message: ChatMessage, payload: dict[str, Any]) -> None:
    payload = {**payload, "undone": True}
    message.content = "[UI_ACTION] " + json.dumps(payload, ensure_ascii=False, default=str)
    meta = _parse_meta(message.meta_json)
    meta["undone"] = True
    message.meta_json = json.dumps(meta, ensure_ascii=False)


def is_hidden_chat_meta(meta: dict[str, Any] | None) -> bool:
    if not meta:
        return False
    return bool(meta.get("hidden") or meta.get("source") == "ui")
