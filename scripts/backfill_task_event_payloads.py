#!/usr/bin/env python3
"""Backfill malformed task replay payloads in agent_execution_events.

Usage:
    uv run python scripts/backfill_task_event_payloads.py --dry-run
    uv run python scripts/backfill_task_event_payloads.py --conversation-id <conversation-id> --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select, update


def _ensure_project_root_on_path() -> None:
    """Ensure the repository root is importable when running as a script."""
    project_root = Path(__file__).parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


@dataclass
class RepairStats:
    """Summary of scanned and repaired task events."""

    scanned: int = 0
    malformed_task_list_updated: int = 0
    repaired_task_list_updated: int = 0
    malformed_task_updated: int = 0


def _is_valid_task_list_event_data(conversation_id: str, event_data: object) -> bool:
    """Return True when task_list_updated already contains a usable snapshot."""
    return (
        isinstance(event_data, Mapping)
        and isinstance(event_data.get("tasks"), list)
        and event_data.get("conversation_id") == conversation_id
    )


def _is_valid_task_updated_event_data(conversation_id: str, event_data: object) -> bool:
    """Return True when task_updated can be replayed as a delta."""
    return (
        isinstance(event_data, Mapping)
        and event_data.get("conversation_id") == conversation_id
        and isinstance(event_data.get("task_id"), str)
        and bool(event_data.get("task_id"))
        and isinstance(event_data.get("status"), str)
        and bool(event_data.get("status"))
    )


async def backfill_task_event_payloads(
    *,
    conversation_id: str | None,
    apply_changes: bool,
) -> RepairStats:
    """Repair malformed task_list_updated payloads and report broken task_updated rows."""
    _ensure_project_root_on_path()

    from src.infrastructure.adapters.secondary.persistence.database import async_session_factory
    from src.infrastructure.adapters.secondary.persistence.models import (
        AgentExecutionEvent as DBAgentExecutionEvent,
    )
    from src.infrastructure.adapters.secondary.persistence.sql_agent_task_repository import (
        SqlAgentTaskRepository,
    )

    stats = RepairStats()

    async with async_session_factory() as session, session.begin():
        stmt = select(
            DBAgentExecutionEvent.id,
            DBAgentExecutionEvent.conversation_id,
            DBAgentExecutionEvent.event_type,
            DBAgentExecutionEvent.event_data,
        ).where(DBAgentExecutionEvent.event_type.in_(("task_list_updated", "task_updated")))
        if conversation_id:
            stmt = stmt.where(DBAgentExecutionEvent.conversation_id == conversation_id)
        stmt = stmt.order_by(
            DBAgentExecutionEvent.conversation_id.asc(),
            DBAgentExecutionEvent.event_time_us.asc(),
            DBAgentExecutionEvent.event_counter.asc(),
        )

        rows = (await session.execute(stmt)).all()
        task_repo = SqlAgentTaskRepository(session)
        snapshot_cache: dict[str, list[dict[str, Any]]] = {}

        async def _load_task_snapshot(row_conversation_id: str) -> list[dict[str, Any]]:
            if row_conversation_id not in snapshot_cache:
                tasks = await task_repo.find_by_conversation(row_conversation_id)
                snapshot_cache[row_conversation_id] = [task.to_dict() for task in tasks]
            return snapshot_cache[row_conversation_id]

        for event_id, row_conversation_id, event_type, event_data in rows:
            stats.scanned += 1

            if event_type == "task_list_updated":
                if _is_valid_task_list_event_data(row_conversation_id, event_data):
                    continue

                stats.malformed_task_list_updated += 1
                repaired_payload = {
                    "conversation_id": row_conversation_id,
                    "tasks": await _load_task_snapshot(row_conversation_id),
                }
                if apply_changes:
                    await session.execute(
                        update(DBAgentExecutionEvent)
                        .where(DBAgentExecutionEvent.id == event_id)
                        .values(event_data=repaired_payload)
                    )
                stats.repaired_task_list_updated += 1
                continue

            if not _is_valid_task_updated_event_data(row_conversation_id, event_data):
                stats.malformed_task_updated += 1

    return stats


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repair malformed task replay payloads in agent_execution_events.",
    )
    parser.add_argument(
        "--conversation-id",
        help="Only scan a single conversation.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist repaired task_list_updated payloads.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the repair summary without modifying rows (default behaviour).",
    )
    return parser


async def _run() -> int:
    args = _build_parser().parse_args()
    apply_changes = args.apply and not args.dry_run
    stats = await backfill_task_event_payloads(
        conversation_id=args.conversation_id,
        apply_changes=apply_changes,
    )

    mode = "apply" if apply_changes else "dry-run"
    print(f"[task-event-backfill] mode={mode}")
    if args.conversation_id:
        print(f"[task-event-backfill] conversation_id={args.conversation_id}")
    print(f"[task-event-backfill] scanned={stats.scanned}")
    print(
        "[task-event-backfill] malformed_task_list_updated="
        f"{stats.malformed_task_list_updated}"
    )
    print(
        "[task-event-backfill] repaired_task_list_updated="
        f"{stats.repaired_task_list_updated}"
    )
    print(f"[task-event-backfill] malformed_task_updated={stats.malformed_task_updated}")

    if not apply_changes:
        print("[task-event-backfill] No rows updated. Re-run with --apply to persist repairs.")
    if stats.malformed_task_updated:
        print(
            "[task-event-backfill] Note: malformed task_updated rows were not rewritten; "
            "runtime replay now converts them to full task snapshots."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
