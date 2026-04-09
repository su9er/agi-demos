"""Shared HITL utilities for request identity, scoping, and text sanitization."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from html import escape, unescape
from typing import Any, cast

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_hitl_text(value: object) -> str | None:
    """Return a plain-text-safe HITL string or None when it becomes empty."""
    if not isinstance(value, str):
        return None
    candidate = unescape(_CONTROL_CHARS_RE.sub("", value)).strip()
    if not candidate:
        return None
    return escape(candidate)


def sanitize_hitl_scalar(value: object) -> bool | int | float | str | None:
    """Return a safe scalar value for HITL payloads."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return sanitize_hitl_text(value)


def sanitize_hitl_sequence(value: object) -> list[bool | int | float | str] | None:
    """Return a safe list value for HITL payloads."""
    if not isinstance(value, (list, tuple)):
        return None
    sanitized_items: list[bool | int | float | str] = []
    for item in value:
        sanitized_item = sanitize_hitl_scalar(item)
        if sanitized_item is None:
            return None
        sanitized_items.append(sanitized_item)
    return sanitized_items or None


def sanitize_hitl_context(raw_context: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a context dict that contains only safe scalar or list values."""
    if raw_context is None:
        return {}

    sanitized_context: dict[str, Any] = {}
    for key, value in raw_context.items():
        if not isinstance(key, str):
            continue
        sanitized_key = sanitize_hitl_text(key)
        if sanitized_key is None:
            continue
        sanitized_scalar = sanitize_hitl_scalar(value)
        if sanitized_scalar is not None:
            sanitized_context[sanitized_key] = sanitized_scalar
            continue
        sanitized_sequence = sanitize_hitl_sequence(value)
        if sanitized_sequence is not None:
            sanitized_context[sanitized_key] = sanitized_sequence
    return sanitized_context


def build_stable_hitl_request_id(
    prefix: str,
    *,
    tenant_id: str | None,
    project_id: str | None,
    conversation_id: str | None,
    message_id: str | None,
    call_id: str | None,
    payload: Mapping[str, Any],
) -> str:
    """Build a deterministic HITL request id from scope plus full payload semantics."""
    seed_payload = {
        "tenant_id": tenant_id or "",
        "project_id": project_id or "",
        "conversation_id": conversation_id or "",
        "message_id": message_id or "",
        "call_id": call_id or "",
        "payload": payload,
    }
    seed = json.dumps(
        seed_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return f"{prefix}_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]}"


def scope_hitl_handler[T](
    base_handler: T,
    *,
    tenant_id: str | None,
    project_id: str | None,
    conversation_id: str | None,
    message_id: str | None,
) -> T:
    """Clone a Ray HITL handler into the current execution scope when possible."""
    if base_handler is None:
        return base_handler

    from src.infrastructure.agent.hitl.ray_hitl_handler import RayHITLHandler

    if not isinstance(base_handler, RayHITLHandler):
        return base_handler

    resolved_tenant_id = tenant_id or base_handler.tenant_id
    resolved_project_id = project_id if project_id is not None else base_handler.project_id
    resolved_conversation_id = conversation_id or base_handler.conversation_id
    resolved_message_id = base_handler.message_id if message_id is None else message_id

    return cast(
        T,
        base_handler.with_scope(
            tenant_id=resolved_tenant_id,
            project_id=resolved_project_id,
            conversation_id=resolved_conversation_id,
            message_id=resolved_message_id,
        ),
    )
