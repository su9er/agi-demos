"""`memstack logs` — dump recent execution events for a conversation.

Reads from GET /agent/conversations/{id}/events, which returns the
persisted timeline (assistant messages, tool calls, plan steps, HITL,
artifacts, completion). Intended for operators triaging a stuck or
failed conversation without opening the web UI.
"""

from __future__ import annotations

from typing import Any

import click

from ..auth import AuthError, resolve_api_key
from ..client import ApiError, die, emit, request


def _key_or_die(flag: str | None) -> str:
    try:
        return resolve_api_key(flag)
    except AuthError as e:
        die(str(e), code=2)
        raise  # unreachable


def _summarize(event: dict[str, Any]) -> str:
    """One-line human summary of an execution event."""
    etype = event.get("event_type") or event.get("type") or "?"
    seq = event.get("sequence_number")
    seq_str = f"#{seq} " if seq is not None else ""
    ts = event.get("created_at") or event.get("timestamp") or ""
    data = event.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    hint = ""
    if etype == "assistant_message":
        text = data.get("content") or data.get("text") or ""
        hint = text[:120].replace("\n", " ")
    elif etype in ("tool_call", "tool_invoke", "tool_start", "tool_result", "tool_complete"):
        hint = str(data.get("tool_name") or data.get("name") or "")
    elif etype == "error":
        hint = str(data.get("message") or data.get("error") or "")[:200]
    elif etype == "complete":
        hint = str(data.get("reason") or data.get("status") or "")
    elif etype == "hitl_request":
        hint = f"hitl:{data.get('hitl_type') or ''}"
    elif etype == "artifact_created":
        hint = str(data.get("artifact_id") or data.get("id") or "")

    return f"{seq_str}{ts:<27} {etype:<22} {hint}".rstrip()


@click.command("logs", help="Dump recent execution events for a conversation.")
@click.argument("conversation_id")
@click.option(
    "--limit",
    default=200,
    show_default=True,
    help="Maximum events to return (server caps at 10000).",
)
@click.option(
    "--from-sequence",
    "from_seq",
    default=0,
    show_default=True,
    help="Return only events with sequence_number >= this.",
)
@click.option(
    "--type",
    "event_type",
    help="Filter by event_type (client-side, after fetch).",
)
@click.pass_context
def logs(
    ctx: click.Context,
    conversation_id: str,
    limit: int,
    from_seq: int,
    event_type: str | None,
) -> None:
    key = _key_or_die(ctx.obj.get("api_key"))
    params: dict[str, Any] = {"limit": limit, "from_sequence": from_seq}

    try:
        data: Any = request(
            "GET",
            f"/agent/conversations/{conversation_id}/events",
            api_key=key,
            params=params,
        )
    except ApiError as e:
        die(str(e))

    events = data.get("events") if isinstance(data, dict) else data
    events = events or []

    if event_type:
        events = [
            e for e in events if (e.get("event_type") or e.get("type")) == event_type
        ]

    if ctx.obj.get("json"):
        emit(events, as_json=True)
        return

    if not events:
        print("(no events)")
        return

    for e in events:
        print(_summarize(e))
    has_more = bool(data.get("has_more")) if isinstance(data, dict) else False
    if has_more:
        print(f"... (more events; pass --limit higher or --from-sequence {events[-1].get('sequence_number', 0) + 1})")
