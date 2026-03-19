from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agent.subagent.orphan_sweeper import OrphanSweeper


def _make_state(
    *,
    conversation_id: str = "conv-1",
    subagent_id: str = "sa-1",
    subagent_name: str = "researcher",
    started_at: datetime | None = None,
) -> MagicMock:
    state = MagicMock()
    state.conversation_id = conversation_id
    state.subagent_id = subagent_id
    state.subagent_name = subagent_name
    state.started_at = started_at
    return state


def _make_done_task() -> MagicMock:
    task = MagicMock(spec=asyncio.Task)
    task.done.return_value = True
    return task


def _make_running_task() -> MagicMock:
    task = MagicMock(spec=asyncio.Task)
    task.done.return_value = False
    return task


@pytest.mark.unit
class TestOrphanSweeper:
    async def test_sweep_removes_done_tasks(self) -> None:
        tracker = MagicMock()
        sweeper = OrphanSweeper(tracker=tracker, redis_client=None, timeout_seconds=300.0)

        tasks: dict[str, asyncio.Task[object]] = {
            "eid-1": _make_done_task(),
            "eid-2": _make_done_task(),
        }

        removed = await sweeper.sweep(tasks)

        assert sorted(removed) == ["eid-1", "eid-2"]
        assert len(tasks) == 0
        tracker.get_state_by_execution_id.assert_not_called()
        assert sweeper.consume_pending_events() == []

    async def test_sweep_timeout_kills_task(self) -> None:
        old_start = datetime.now(UTC) - timedelta(seconds=600)
        state = _make_state(started_at=old_start)
        tracker = MagicMock()
        tracker.get_state_by_execution_id.return_value = state

        task = _make_running_task()
        tasks: dict[str, asyncio.Task[object]] = {"eid-timeout": task}

        sweeper = OrphanSweeper(tracker=tracker, redis_client=None, timeout_seconds=300.0)
        removed = await sweeper.sweep(tasks)

        assert removed == ["eid-timeout"]
        assert len(tasks) == 0
        task.cancel.assert_called_once()
        tracker.fail.assert_called_once_with(
            "eid-timeout",
            "conv-1",
            error="Timed out after 300.0s (orphan sweep)",
        )

    async def test_sweep_cancel_signal_kills_task(self) -> None:
        state = _make_state(started_at=datetime.now(UTC))
        tracker = MagicMock()
        tracker.get_state_by_execution_id.return_value = state

        redis = AsyncMock()
        cancel_payload = json.dumps({"reason": "user requested"})
        redis.get.return_value = cancel_payload

        task = _make_running_task()
        tasks: dict[str, asyncio.Task[object]] = {"eid-cancel": task}

        sweeper = OrphanSweeper(tracker=tracker, redis_client=redis, timeout_seconds=300.0)
        removed = await sweeper.sweep(tasks)

        assert removed == ["eid-cancel"]
        assert len(tasks) == 0
        task.cancel.assert_called_once()
        tracker.fail.assert_called_once_with(
            "eid-cancel",
            "conv-1",
            error="Cancelled: user requested",
        )
        redis.delete.assert_awaited_once_with("subagent:cancel:eid-cancel")

    async def test_sweep_skips_no_state(self) -> None:
        tracker = MagicMock()
        tracker.get_state_by_execution_id.return_value = None

        task = _make_running_task()
        tasks: dict[str, asyncio.Task[object]] = {"eid-nostate": task}

        sweeper = OrphanSweeper(tracker=tracker, redis_client=None, timeout_seconds=300.0)
        removed = await sweeper.sweep(tasks)

        assert removed == []
        assert len(tasks) == 1
        task.cancel.assert_not_called()

    async def test_sweep_skips_no_started_at(self) -> None:
        state = _make_state(started_at=None)
        tracker = MagicMock()
        tracker.get_state_by_execution_id.return_value = state

        task = _make_running_task()
        tasks: dict[str, asyncio.Task[object]] = {"eid-nostart": task}

        sweeper = OrphanSweeper(tracker=tracker, redis_client=None, timeout_seconds=300.0)
        removed = await sweeper.sweep(tasks)

        assert removed == []
        assert len(tasks) == 1
        task.cancel.assert_not_called()

    async def test_sweep_emits_killed_event_on_timeout(self) -> None:
        old_start = datetime.now(UTC) - timedelta(seconds=600)
        state = _make_state(
            subagent_id="sa-timeout",
            subagent_name="coder",
            started_at=old_start,
        )
        tracker = MagicMock()
        tracker.get_state_by_execution_id.return_value = state

        task = _make_running_task()
        tasks: dict[str, asyncio.Task[object]] = {"eid-t": task}

        sweeper = OrphanSweeper(tracker=tracker, redis_client=None, timeout_seconds=300.0)
        await sweeper.sweep(tasks)

        events = sweeper.consume_pending_events()
        assert len(events) == 1
        event = events[0]
        assert event["type"] == "subagent_killed"
        assert event["data"]["subagent_id"] == "sa-timeout"
        assert event["data"]["subagent_name"] == "coder"
        assert event["data"]["kill_reason"] == "orphan_sweep"

    async def test_sweep_emits_killed_event_on_cancel(self) -> None:
        state = _make_state(
            subagent_id="sa-cancel",
            subagent_name="writer",
            started_at=datetime.now(UTC),
        )
        tracker = MagicMock()
        tracker.get_state_by_execution_id.return_value = state

        redis = AsyncMock()
        redis.get.return_value = json.dumps({"reason": "manual cancel"})

        task = _make_running_task()
        tasks: dict[str, asyncio.Task[object]] = {"eid-c": task}

        sweeper = OrphanSweeper(tracker=tracker, redis_client=redis, timeout_seconds=300.0)
        await sweeper.sweep(tasks)

        events = sweeper.consume_pending_events()
        assert len(events) == 1
        event = events[0]
        assert event["type"] == "subagent_killed"
        assert event["data"]["subagent_id"] == "sa-cancel"
        assert event["data"]["subagent_name"] == "writer"
        assert event["data"]["kill_reason"] == "manual cancel"

    async def test_consume_pending_events_clears_list(self) -> None:
        old_start = datetime.now(UTC) - timedelta(seconds=600)
        state = _make_state(started_at=old_start)
        tracker = MagicMock()
        tracker.get_state_by_execution_id.return_value = state

        tasks: dict[str, asyncio.Task[object]] = {
            "eid-a": _make_running_task(),
            "eid-b": _make_running_task(),
        }

        sweeper = OrphanSweeper(tracker=tracker, redis_client=None, timeout_seconds=300.0)
        await sweeper.sweep(tasks)

        events = sweeper.consume_pending_events()
        assert len(events) == 2

        events_again = sweeper.consume_pending_events()
        assert events_again == []

    async def test_reconcile_on_startup_detects_orphans(self) -> None:
        tracker = MagicMock()
        sweeper = OrphanSweeper(tracker=tracker, redis_client=None, timeout_seconds=300.0)

        now = datetime.now(UTC)
        stale_runs: list[tuple[str, str, str, datetime | None]] = [
            ("run-1", "coder", "conv-1", now - timedelta(seconds=120)),
            ("run-2", "researcher", "conv-2", None),
        ]

        orphaned = await sweeper.reconcile_on_startup(stale_runs)

        assert orphaned == ["run-1", "run-2"]
        events = sweeper.consume_pending_events()
        assert len(events) == 2

        e1 = events[0]
        assert e1["type"] == "subagent_orphan_detected"
        assert e1["data"]["run_id"] == "run-1"
        assert e1["data"]["subagent_name"] == "coder"
        assert e1["data"]["reason"] == "parent_gone"
        assert e1["data"]["action_taken"] == "marked_failed"
        assert e1["data"]["age_seconds"] > 100

        e2 = events[1]
        assert e2["type"] == "subagent_orphan_detected"
        assert e2["data"]["run_id"] == "run-2"
        assert e2["data"]["subagent_name"] == "researcher"
        assert e2["data"]["age_seconds"] == 0.0

    async def test_sweep_mixed_done_and_timeout(self) -> None:
        old_start = datetime.now(UTC) - timedelta(seconds=600)
        state = _make_state(started_at=old_start)
        tracker = MagicMock()
        tracker.get_state_by_execution_id.return_value = state

        tasks: dict[str, asyncio.Task[object]] = {
            "eid-done": _make_done_task(),
            "eid-timed": _make_running_task(),
        }

        sweeper = OrphanSweeper(tracker=tracker, redis_client=None, timeout_seconds=300.0)
        removed = await sweeper.sweep(tasks)

        assert sorted(removed) == ["eid-done", "eid-timed"]
        assert len(tasks) == 0
        events = sweeper.consume_pending_events()
        assert len(events) == 1
        assert events[0]["type"] == "subagent_killed"

    async def test_sweep_redis_error_does_not_crash(self) -> None:
        state = _make_state(started_at=None)
        tracker = MagicMock()
        tracker.get_state_by_execution_id.return_value = state

        redis = AsyncMock()
        redis.get.side_effect = ConnectionError("Redis down")

        task = _make_running_task()
        tasks: dict[str, asyncio.Task[object]] = {"eid-err": task}

        sweeper = OrphanSweeper(tracker=tracker, redis_client=redis, timeout_seconds=300.0)
        removed = await sweeper.sweep(tasks)

        assert removed == []
        assert len(tasks) == 1
        task.cancel.assert_not_called()
