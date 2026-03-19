"""Orphan detection and cleanup for background SubAgent tasks.

Extracted from BackgroundExecutor._sweep_orphans() to enable:
1. Standalone testability
2. Reuse across BackgroundExecutor and actor startup reconciliation
3. Emission of SubAgentOrphanDetectedEvent for observability
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from redis.asyncio import Redis as AsyncRedis

from src.domain.events.agent_events import (
    SubAgentKilledEvent,
    SubAgentOrphanDetectedEvent,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class _SubAgentStateProto(Protocol):
    conversation_id: str
    subagent_id: str
    subagent_name: str
    started_at: datetime | None


class SweepTarget(Protocol):
    """Protocol for state access needed by OrphanSweeper.

    StateTracker already satisfies this protocol.
    """

    def get_state_by_execution_id(
        self,
        execution_id: str,
    ) -> _SubAgentStateProto | None: ...

    def fail(
        self,
        execution_id: str,
        conversation_id: str,
        *,
        error: str,
    ) -> _SubAgentStateProto | None: ...


class OrphanSweeper:
    """Detects and cleans up orphaned SubAgent tasks.

    Handles three sweep categories:
    1. Done tasks -- simply remove from task dict
    2. Redis cancel signals -- cancel task, mark failed, emit SubAgentKilledEvent
    3. Timeout -- cancel task, mark failed, emit SubAgentKilledEvent

    Additionally provides startup reconciliation to detect orphans
    from previous process incarnations.
    """

    def __init__(
        self,
        tracker: SweepTarget,
        redis_client: AsyncRedis | None = None,
        timeout_seconds: float = 300.0,
    ) -> None:
        self._tracker = tracker
        self._redis = redis_client
        self._timeout_seconds = timeout_seconds
        self._pending_events: list[dict[str, Any]] = []

    async def sweep(self, tasks: dict[str, asyncio.Task[Any]]) -> list[str]:
        """Scan tasks and clean up done, timed-out, or cancel-signalled entries.

        Args:
            tasks: Mutable dict of execution_id -> asyncio.Task.
                   Swept entries are removed in-place.

        Returns:
            List of execution_ids that were removed.
        """
        now = datetime.now(UTC)
        to_remove: list[str] = []

        for eid, task in list(tasks.items()):
            if task.done():
                to_remove.append(eid)
                continue

            state = self._tracker.get_state_by_execution_id(eid)
            if state is None:
                continue

            # Check for Redis cancel signal
            if self._redis is not None:
                try:
                    cancel_key = f"subagent:cancel:{eid}"
                    cancel_data_raw = await self._redis.get(cancel_key)
                    if cancel_data_raw is not None:
                        task.cancel()
                        cancel_info = json.loads(cancel_data_raw)
                        reason = cancel_info.get("reason", "Cancelled by user")
                        self._tracker.fail(
                            eid,
                            state.conversation_id,
                            error=f"Cancelled: {reason}",
                        )
                        to_remove.append(eid)
                        self._pending_events.append(
                            dict(
                                SubAgentKilledEvent(
                                    subagent_id=state.subagent_id,
                                    subagent_name=state.subagent_name,
                                    kill_reason=reason,
                                ).to_event_dict(),
                            ),
                        )
                        await self._redis.delete(cancel_key)
                        logger.info(
                            "[OrphanSweeper] Cancelled %s via Redis signal (%s, reason=%s)",
                            eid,
                            state.subagent_name,
                            reason,
                        )
                        continue
                except Exception:
                    logger.warning(
                        "[OrphanSweeper] Error checking cancel signal for %s",
                        eid,
                        exc_info=True,
                    )

            if state.started_at is None:
                continue

            elapsed = (now - state.started_at).total_seconds()
            if elapsed > self._timeout_seconds:
                task.cancel()
                self._tracker.fail(
                    eid,
                    state.conversation_id,
                    error=f"Timed out after {self._timeout_seconds}s (orphan sweep)",
                )
                to_remove.append(eid)
                self._pending_events.append(
                    dict(
                        SubAgentKilledEvent(
                            subagent_id=state.subagent_id,
                            subagent_name=state.subagent_name,
                            kill_reason="orphan_sweep",
                        ).to_event_dict(),
                    ),
                )
                logger.warning(
                    "[OrphanSweeper] Killed orphan %s (%s, %.0fs elapsed)",
                    eid,
                    state.subagent_name,
                    elapsed,
                )

        for eid in to_remove:
            tasks.pop(eid, None)

        return to_remove

    async def reconcile_on_startup(
        self,
        stale_runs: list[tuple[str, str, str, datetime | None]],
    ) -> list[str]:
        """Check for orphaned runs from previous process incarnations.

        Called at actor/process startup to detect runs that were in-flight
        when the previous incarnation crashed.

        Args:
            stale_runs: List of (run_id, subagent_name, conversation_id, started_at)
                tuples representing runs that were active but have no corresponding
                live task.

        Returns:
            List of orphaned run_ids detected.
        """
        now = datetime.now(UTC)
        orphaned: list[str] = []

        for run_id, subagent_name, conversation_id, started_at in stale_runs:
            age = (now - started_at).total_seconds() if started_at is not None else 0.0
            self._pending_events.append(
                dict(
                    SubAgentOrphanDetectedEvent(
                        run_id=run_id,
                        subagent_name=subagent_name,
                        conversation_id=conversation_id,
                        reason="parent_gone",
                        age_seconds=age,
                        action_taken="marked_failed",
                    ).to_event_dict(),
                ),
            )
            orphaned.append(run_id)
            logger.warning(
                "[OrphanSweeper] Detected orphan from previous incarnation: %s (%s, %.0fs old)",
                run_id,
                subagent_name,
                age,
            )

        return orphaned

    def consume_pending_events(self) -> list[dict[str, Any]]:
        """Consume and clear pending events (SubAgentKilledEvent, SubAgentOrphanDetectedEvent)."""
        events = list(self._pending_events)
        self._pending_events.clear()
        return events
