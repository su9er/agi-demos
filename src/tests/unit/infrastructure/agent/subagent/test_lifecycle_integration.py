"""Integration tests for Phase 1 multi-agent lifecycle hardening.

Wires 2+ real components together with mocks only for external dependencies
(Redis, filesystem). Covers SpawnValidator+Policy, SpawnValidator+RunRegistry,
AnnounceService retry+events, OrphanSweeper+StateTracker/Redis,
SubAgentRun lifecycle, and full spawn-to-freeze flow.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.domain.model.agent.announce_config import AnnounceConfig
from src.domain.model.agent.spawn_policy import (
    SpawnPolicy,
    SpawnRejectionCode,
)
from src.domain.model.agent.subagent_run import SubAgentRun, SubAgentRunStatus
from src.infrastructure.agent.subagent.announce_service import AnnounceService
from src.infrastructure.agent.subagent.orphan_sweeper import OrphanSweeper
from src.infrastructure.agent.subagent.run_registry import SubAgentRunRegistry
from src.infrastructure.agent.subagent.spawn_validator import SpawnValidator


def _make_registry() -> SubAgentRunRegistry:
    return SubAgentRunRegistry()


def _make_validator(
    *,
    max_depth: int = 2,
    max_active_runs: int = 4,
    max_children_per_requester: int = 2,
    allowed_subagents: frozenset[str] | None = None,
    registry: SubAgentRunRegistry | None = None,
) -> tuple[SpawnValidator, SubAgentRunRegistry]:
    reg = registry or _make_registry()
    policy = SpawnPolicy(
        max_depth=max_depth,
        max_active_runs=max_active_runs,
        max_children_per_requester=max_children_per_requester,
        allowed_subagents=allowed_subagents,
    )
    return SpawnValidator(policy=policy, run_registry=reg), reg


@dataclass
class _FakeState:
    conversation_id: str
    subagent_id: str
    subagent_name: str
    started_at: datetime | None


class _FakeTracker:
    """Minimal SweepTarget implementation for OrphanSweeper tests."""

    def __init__(self) -> None:
        self.states: dict[str, _FakeState] = {}
        self.failed: list[tuple[str, str, str]] = []

    def get_state_by_execution_id(self, execution_id: str) -> _FakeState | None:
        return self.states.get(execution_id)

    def fail(
        self,
        execution_id: str,
        conversation_id: str,
        *,
        error: str,
    ) -> _FakeState | None:
        self.failed.append((execution_id, conversation_id, error))
        state = self.states.get(execution_id)
        return state


@pytest.mark.unit
class TestSpawnValidatorWithPolicy:
    async def test_depth_exceeded_rejected(self) -> None:
        validator, _ = _make_validator(max_depth=1)

        result = validator.validate("researcher", current_depth=1, conversation_id="c1")

        assert result.allowed is False
        assert result.rejection_code == SpawnRejectionCode.DEPTH_EXCEEDED

    async def test_depth_within_limit_allowed(self) -> None:
        validator, _ = _make_validator(max_depth=3)

        result = validator.validate("researcher", current_depth=2, conversation_id="c1")

        assert result.allowed is True

    async def test_allowlist_rejects_unknown_subagent(self) -> None:
        validator, _ = _make_validator(
            allowed_subagents=frozenset({"coder", "reviewer"}),
        )

        result = validator.validate("hacker", current_depth=0, conversation_id="c1")

        assert result.allowed is False
        assert result.rejection_code == SpawnRejectionCode.SUBAGENT_NOT_ALLOWED

    async def test_allowlist_permits_known_subagent(self) -> None:
        validator, _ = _make_validator(
            allowed_subagents=frozenset({"coder", "reviewer"}),
        )

        result = validator.validate("coder", current_depth=0, conversation_id="c1")

        assert result.allowed is True


@pytest.mark.unit
class TestSpawnValidatorWithRunRegistry:
    async def test_children_limit_blocks_when_active_runs_hit_cap(self) -> None:
        registry = _make_registry()
        validator, _ = _make_validator(
            max_children_per_requester=2,
            max_active_runs=10,
            registry=registry,
        )
        registry.create_run(conversation_id="c1", subagent_name="a", task="t1")
        registry.create_run(conversation_id="c1", subagent_name="b", task="t2")

        result = validator.validate("c", current_depth=0, conversation_id="c1")

        assert result.allowed is False
        assert result.rejection_code == SpawnRejectionCode.CHILDREN_EXCEEDED

    async def test_global_concurrency_blocks_across_conversations(self) -> None:
        registry = _make_registry()
        validator, _ = _make_validator(
            max_children_per_requester=10,
            max_active_runs=3,
            registry=registry,
        )
        registry.create_run(conversation_id="c1", subagent_name="a", task="t1")
        registry.create_run(conversation_id="c2", subagent_name="b", task="t2")
        registry.create_run(conversation_id="c3", subagent_name="c", task="t3")

        result = validator.validate("d", current_depth=0, conversation_id="c4")

        assert result.allowed is False
        assert result.rejection_code == SpawnRejectionCode.CONCURRENCY_EXCEEDED
        assert result.context["total_active"] == 3

    async def test_completed_runs_do_not_count_toward_limits(self) -> None:
        registry = _make_registry()
        validator, _ = _make_validator(
            max_children_per_requester=2,
            max_active_runs=10,
            registry=registry,
        )
        run = registry.create_run(conversation_id="c1", subagent_name="a", task="t1")
        registry.mark_running("c1", run.run_id)
        registry.mark_completed("c1", run.run_id, summary="done")

        result = validator.validate("b", current_depth=0, conversation_id="c1")

        assert result.allowed is True


@pytest.mark.unit
class TestAnnounceServiceRetryFlow:
    async def test_transient_then_success_produces_events(self) -> None:
        redis = AsyncMock()
        redis.xadd.side_effect = [ConnectionError("lost"), AsyncMock(return_value="1-0")]
        config = AnnounceConfig(max_retries=3, retry_delay_ms=0)
        svc = AnnounceService(redis_client=redis, config=config)

        ok = await svc.publish_announce(
            agent_id="a1",
            parent_session_id="p1",
            child_session_id="c1",
            result_content="result",
            success=True,
        )

        assert ok is True
        assert redis.xadd.await_count == 2

        events = svc.consume_pending_events()
        assert len(events) == 1
        evt = events[0]
        assert evt.attempt == 1
        assert evt.error_category == "transient"
        assert evt.agent_id == "a1"
        assert evt.session_id == "c1"

    async def test_all_transient_retries_exhausted_returns_false(self) -> None:
        redis = AsyncMock()
        redis.xadd.side_effect = [
            ConnectionError("f1"),
            ConnectionError("f2"),
            ConnectionError("f3"),
        ]
        config = AnnounceConfig(max_retries=2, retry_delay_ms=0)
        svc = AnnounceService(redis_client=redis, config=config)

        ok = await svc.publish_announce(
            agent_id="a1",
            parent_session_id="p1",
            child_session_id="c1",
            result_content="x",
            success=False,
        )

        assert ok is False
        assert redis.xadd.await_count == 3

        events = svc.consume_pending_events()
        assert len(events) == 2
        assert events[0].attempt == 1
        assert events[1].attempt == 2

    async def test_consume_events_clears_buffer(self) -> None:
        redis = AsyncMock()
        redis.xadd.side_effect = [TimeoutError("slow"), AsyncMock(return_value="1-0")]
        config = AnnounceConfig(max_retries=3, retry_delay_ms=0)
        svc = AnnounceService(redis_client=redis, config=config)

        await svc.publish_announce(
            agent_id="a1",
            parent_session_id="p1",
            child_session_id="c1",
            result_content="r",
            success=True,
        )

        first_batch = svc.consume_pending_events()
        assert len(first_batch) == 1

        second_batch = svc.consume_pending_events()
        assert second_batch == []


@pytest.mark.unit
class TestOrphanSweeperWithStateTracker:
    async def test_timeout_kills_task_and_emits_event(self) -> None:
        tracker = _FakeTracker()
        sweeper = OrphanSweeper(tracker=tracker, redis_client=None, timeout_seconds=10.0)

        long_ago = datetime.now(UTC) - timedelta(seconds=60)
        tracker.states["eid-1"] = _FakeState(
            conversation_id="c1",
            subagent_id="sa-1",
            subagent_name="researcher",
            started_at=long_ago,
        )
        mock_task = AsyncMock(spec=asyncio.Task)
        mock_task.done.return_value = False
        tasks: dict[str, asyncio.Task[object]] = {"eid-1": mock_task}

        removed = await sweeper.sweep(tasks)

        assert "eid-1" in removed
        assert "eid-1" not in tasks
        mock_task.cancel.assert_called_once()
        assert len(tracker.failed) == 1
        assert tracker.failed[0][0] == "eid-1"

        events = sweeper.consume_pending_events()
        assert len(events) == 1
        assert events[0]["data"]["subagent_name"] == "researcher"
        assert events[0]["data"]["kill_reason"] == "orphan_sweep"

    async def test_done_task_removed_without_killing(self) -> None:
        tracker = _FakeTracker()
        sweeper = OrphanSweeper(tracker=tracker, redis_client=None, timeout_seconds=300.0)

        mock_task = AsyncMock(spec=asyncio.Task)
        mock_task.done.return_value = True
        tasks: dict[str, asyncio.Task[object]] = {"eid-done": mock_task}

        removed = await sweeper.sweep(tasks)

        assert "eid-done" in removed
        assert "eid-done" not in tasks
        mock_task.cancel.assert_not_called()
        assert sweeper.consume_pending_events() == []


@pytest.mark.unit
class TestOrphanSweeperWithRedisCancel:
    async def test_redis_cancel_signal_kills_task(self) -> None:
        tracker = _FakeTracker()
        redis = AsyncMock()
        redis.get.return_value = json.dumps({"reason": "User requested cancel"})
        redis.delete.return_value = 1
        sweeper = OrphanSweeper(tracker=tracker, redis_client=redis, timeout_seconds=300.0)

        tracker.states["eid-2"] = _FakeState(
            conversation_id="c2",
            subagent_id="sa-2",
            subagent_name="builder",
            started_at=datetime.now(UTC),
        )
        mock_task = AsyncMock(spec=asyncio.Task)
        mock_task.done.return_value = False
        tasks: dict[str, asyncio.Task[object]] = {"eid-2": mock_task}

        removed = await sweeper.sweep(tasks)

        assert "eid-2" in removed
        mock_task.cancel.assert_called_once()
        redis.get.assert_awaited_once_with("subagent:cancel:eid-2")
        redis.delete.assert_awaited_once_with("subagent:cancel:eid-2")

        events = sweeper.consume_pending_events()
        assert len(events) == 1
        assert events[0]["data"]["kill_reason"] == "User requested cancel"


@pytest.mark.unit
class TestSubAgentRunFrozenLifecycle:
    async def test_full_freeze_lifecycle(self) -> None:
        run = SubAgentRun(conversation_id="c1", subagent_name="analyst", task="analyze data")
        assert run.status == SubAgentRunStatus.PENDING
        assert run.frozen_result_text is None
        assert run.frozen_at is None

        run = run.start()
        assert run.status == SubAgentRunStatus.RUNNING

        run = run.complete(summary="analysis done", tokens_used=500)
        assert run.status == SubAgentRunStatus.COMPLETED
        assert run.summary == "analysis done"

        run = run.freeze_result("Final analysis: metrics look great")
        assert run.status == SubAgentRunStatus.COMPLETED
        assert run.frozen_result_text == "Final analysis: metrics look great"
        assert run.frozen_at is not None

    async def test_freeze_on_failed_run(self) -> None:
        run = SubAgentRun(conversation_id="c1", subagent_name="builder", task="build feature")
        run = run.start()
        run = run.fail(error="compilation error")
        assert run.status == SubAgentRunStatus.FAILED

        run = run.freeze_result("Error captured: compilation error")
        assert run.frozen_result_text == "Error captured: compilation error"

    async def test_double_freeze_raises(self) -> None:
        run = SubAgentRun(conversation_id="c1", subagent_name="s", task="t")
        run = run.start()
        run = run.complete(summary="ok")
        run = run.freeze_result("first freeze")

        with pytest.raises(ValueError, match="already frozen"):
            run.freeze_result("second freeze")

    async def test_freeze_on_pending_raises(self) -> None:
        run = SubAgentRun(conversation_id="c1", subagent_name="s", task="t")

        with pytest.raises(ValueError, match="Cannot freeze"):
            run.freeze_result("nope")


@pytest.mark.unit
class TestFullSpawnToFreezeLifecycle:
    async def test_spawn_run_complete_freeze(self) -> None:
        registry = _make_registry()
        validator, _ = _make_validator(
            max_depth=3,
            max_active_runs=10,
            max_children_per_requester=5,
            registry=registry,
        )

        validation = validator.validate("researcher", current_depth=0, conversation_id="c1")
        assert validation.allowed is True

        run = registry.create_run(
            conversation_id="c1", subagent_name="researcher", task="research topic"
        )
        assert run.status == SubAgentRunStatus.PENDING
        assert registry.count_active_runs("c1") == 1

        updated = registry.mark_running("c1", run.run_id)
        assert updated is not None
        assert updated.status == SubAgentRunStatus.RUNNING

        completed = registry.mark_completed("c1", run.run_id, summary="research done")
        assert completed is not None
        assert completed.status == SubAgentRunStatus.COMPLETED
        assert registry.count_active_runs("c1") == 0

        fetched = registry.get_run("c1", run.run_id)
        assert fetched is not None
        assert fetched.status == SubAgentRunStatus.COMPLETED

    async def test_spawn_blocked_after_limit_then_allowed_after_completion(self) -> None:
        registry = _make_registry()
        validator, _ = _make_validator(
            max_depth=3,
            max_active_runs=10,
            max_children_per_requester=1,
            registry=registry,
        )

        run = registry.create_run(conversation_id="c1", subagent_name="a", task="t1")
        blocked = validator.validate("b", current_depth=0, conversation_id="c1")
        assert blocked.allowed is False
        assert blocked.rejection_code == SpawnRejectionCode.CHILDREN_EXCEEDED

        registry.mark_running("c1", run.run_id)
        registry.mark_completed("c1", run.run_id, summary="done")

        allowed = validator.validate("b", current_depth=0, conversation_id="c1")
        assert allowed.allowed is True
