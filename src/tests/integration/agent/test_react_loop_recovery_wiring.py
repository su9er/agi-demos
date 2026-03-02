"""Integration tests for ReActLoop.run() recovery wiring.

Verifies that the ReActLoop correctly integrates with
SessionRecoveryService when exceptions occur during processing.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.events.agent_events import (
    AgentCompleteEvent,
    AgentDomainEvent,
    AgentErrorEvent,
    AgentStartEvent,
    AgentStatusEvent,
)
from src.infrastructure.agent.core.react_loop import (
    LoopConfig,
    LoopContext,
    ReActLoop,
)
from src.infrastructure.agent.recovery.session_recovery_service import (
    RecoveryResult,
)


def _make_context(
    session_id: str = "sess-001",
    project_id: str = "proj-001",
) -> LoopContext:
    return LoopContext(session_id=session_id, project_id=project_id)


def _make_recovery_service(
    should_retry: bool = False,
    recovered: bool = True,
    strategy: str = "retry_backoff",
    message: str = "ok",
) -> MagicMock:
    service = MagicMock()
    service.attempt_recovery = AsyncMock(
        return_value=RecoveryResult(
            recovered=recovered,
            strategy_used=strategy,
            message=message,
            should_retry=should_retry,
        )
    )
    return service


async def _collect_events(
    loop: ReActLoop,
    messages: list[dict[str, Any]],
    tools: dict[str, Any],
    context: LoopContext,
) -> list[AgentDomainEvent]:
    events: list[AgentDomainEvent] = []
    async for event in loop.run(messages, tools, context):
        events.append(event)
    return events


@pytest.mark.integration
class TestReactLoopRecoveryWiring:
    """Tests for ReActLoop recovery integration with SessionRecoveryService."""

    async def test_recovery_called_on_exception(self) -> None:
        """When _run_iteration raises, recovery service is called.

        Arrange: ReActLoop with mocked recovery service, _run_iteration raises.
        Act: Consume events from loop.run().
        Assert: attempt_recovery was called with session_id and error.
        """
        # Arrange
        recovery_svc = _make_recovery_service(should_retry=False)
        loop = ReActLoop(
            session_recovery_service=recovery_svc,
            config=LoopConfig(max_steps=5),
        )

        error = RuntimeError("LLM provider timeout")
        with patch.object(
            loop,
            "_run_iteration",
            side_effect=error,
        ):
            context = _make_context()
            events = await _collect_events(loop, [], {}, context)

        # Assert
        recovery_svc.attempt_recovery.assert_awaited_once()
        call_kwargs = recovery_svc.attempt_recovery.call_args
        assert call_kwargs.kwargs["session_id"] == "sess-001"
        assert call_kwargs.kwargs["error"] is error

        # Should still yield error event since should_retry=False
        error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
        assert len(error_events) == 1
        assert "LLM provider timeout" in error_events[0].message

    async def test_recovery_retry_re_runs_loop(self) -> None:
        """When recovery returns should_retry=True, loop re-runs.

        Arrange: First _run_iteration raises; recovery says retry.
                 Second run completes normally.
        Act: Consume events.
        Assert: Two AgentStartEvents emitted (initial + retry).
        """
        # Arrange
        recovery_svc = _make_recovery_service(should_retry=True)
        loop = ReActLoop(
            session_recovery_service=recovery_svc,
            config=LoopConfig(max_steps=5),
        )

        call_count = 0

        async def _fake_run_iteration(
            messages: list[dict[str, Any]],
            tools: dict[str, Any],
            context: LoopContext,
        ):  # type: ignore[return]
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient error")
            # On retry, signal completion by setting the result
            loop._last_evaluated_result = loop._last_evaluated_result
            # Yield nothing — let the outer while loop see CONTINUE
            # then on next iteration the step count will exceed
            return
            yield  # make it an async generator

        # Patch the internal method so the first call raises,
        # the second completes. We also need to stop the retry
        # from looping infinitely so patch _process_step on 2nd run.
        first_run_done = False

        original_run = loop.run

        async def patched_run(
            messages: list[dict[str, Any]],
            tools: dict[str, Any],
            context: LoopContext,
        ):  # type: ignore[return]
            nonlocal first_run_done
            if not first_run_done:
                first_run_done = True
                async for event in original_run(messages, tools, context):
                    yield event
            else:
                # Second run succeeds immediately
                yield AgentStartEvent()
                yield AgentCompleteEvent()

        with (
            patch.object(
                loop,
                "_run_iteration",
                side_effect=RuntimeError("transient error"),
            ),
            patch.object(
                loop,
                "run",
                patched_run,
            ),
        ):
            context = _make_context()
            events: list[AgentDomainEvent] = []
            async for event in patched_run([], {}, context):
                events.append(event)

        # Assert
        start_events = [e for e in events if isinstance(e, AgentStartEvent)]
        # At least 2 starts: original + retry
        assert len(start_events) >= 2

        # Recovery status event emitted
        status_events = [
            e
            for e in events
            if isinstance(e, AgentStatusEvent) and getattr(e, "status", "") == "recovery_retry"
        ]
        assert len(status_events) >= 1

    async def test_recovery_no_retry_falls_through(self) -> None:
        """When recovery returns should_retry=False, error event is yielded.

        Arrange: recovery service returns should_retry=False.
        Act: Consume events.
        Assert: AgentErrorEvent is emitted, no retry status event.
        """
        # Arrange
        recovery_svc = _make_recovery_service(
            should_retry=False,
            recovered=False,
            strategy="abort_with_message",
            message="Unrecoverable",
        )
        loop = ReActLoop(
            session_recovery_service=recovery_svc,
            config=LoopConfig(max_steps=5),
        )

        with patch.object(
            loop,
            "_run_iteration",
            side_effect=ValueError("bad state"),
        ):
            context = _make_context()
            events = await _collect_events(loop, [], {}, context)

        # Assert
        error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
        assert len(error_events) == 1

        retry_events = [
            e
            for e in events
            if isinstance(e, AgentStatusEvent) and getattr(e, "status", "") == "recovery_retry"
        ]
        assert len(retry_events) == 0

    async def test_no_recovery_without_service(self) -> None:
        """When no recovery service is configured, error is emitted directly.

        Arrange: ReActLoop without session_recovery_service.
        Act: _run_iteration raises.
        Assert: AgentErrorEvent emitted, no recovery attempted.
        """
        # Arrange
        loop = ReActLoop(config=LoopConfig(max_steps=5))

        with patch.object(
            loop,
            "_run_iteration",
            side_effect=RuntimeError("boom"),
        ):
            context = _make_context()
            events = await _collect_events(loop, [], {}, context)

        # Assert
        error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
        assert len(error_events) == 1
        assert "boom" in error_events[0].message

    async def test_no_recovery_without_session_id(self) -> None:
        """Recovery is skipped when context has no session_id.

        Arrange: ReActLoop with recovery service but context.session_id=''.
        Act: _run_iteration raises.
        Assert: Recovery not called, error event emitted.
        """
        # Arrange
        recovery_svc = _make_recovery_service(should_retry=True)
        loop = ReActLoop(
            session_recovery_service=recovery_svc,
            config=LoopConfig(max_steps=5),
        )

        with patch.object(
            loop,
            "_run_iteration",
            side_effect=RuntimeError("fail"),
        ):
            context = _make_context(session_id="")
            events = await _collect_events(loop, [], {}, context)

        # Assert
        recovery_svc.attempt_recovery.assert_not_awaited()
        error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
        assert len(error_events) == 1
