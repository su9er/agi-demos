"""Integration tests for LLMInvoker._try_failover_on_error.

Verifies the failover decision wiring: chain presence, worthiness
check, and delegation to _attempt_failover.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.agent.llm.invoker import (
    LLMInvoker,
    _FailoverSuccess,
)


def _make_invoker(
    *,
    failover_chain: object | None = None,
) -> LLMInvoker:
    """Build an LLMInvoker with mocked collaborators."""
    retry_policy = MagicMock()
    retry_policy.is_retryable.return_value = False
    retry_policy.calculate_delay.return_value = 0

    cost_tracker = MagicMock()
    cost_tracker.calculate.return_value = MagicMock(
        total_cost=0.0,
    )
    cost_tracker.needs_compaction.return_value = False

    return LLMInvoker(
        retry_policy=retry_policy,
        cost_tracker=cost_tracker,
        failover_chain=failover_chain,
    )


def _failover_kwargs() -> dict[str, object]:
    """Keyword args required by _try_failover_on_error."""
    return {
        "error": RuntimeError("test"),
        "config": MagicMock(),
        "context": MagicMock(),
        "messages": [],
        "tools": {},
        "current_message": MagicMock(),
        "pending_tool_calls": {},
        "work_plan_steps": [],
        "tool_to_step_mapping": {},
        "execute_tool_callback": MagicMock(),
        "result": MagicMock(),
        "current_plan_step": None,
    }


@pytest.mark.integration
class TestInvokerFailoverWiring:
    """Verify _try_failover_on_error decision logic."""

    async def test_failover_skipped_when_no_chain(
        self,
    ) -> None:
        """With failover_chain=None the generator yields
        nothing and returns immediately."""
        # Arrange
        invoker = _make_invoker(failover_chain=None)

        # Act
        events: list[object] = []
        async for ev in invoker._try_failover_on_error(
            **_failover_kwargs(),
        ):
            events.append(ev)

        # Assert
        assert events == []

    @patch(
        "src.infrastructure.llm.failover_chain.is_failover_worthy",
    )
    async def test_failover_skipped_when_not_worthy(
        self,
        mock_worthy: MagicMock,
    ) -> None:
        """When is_failover_worthy returns False, the generator
        yields nothing even if a chain is present."""
        # Arrange
        mock_worthy.return_value = False
        invoker = _make_invoker(
            failover_chain=MagicMock(name="chain"),
        )

        # Act
        events: list[object] = []
        async for ev in invoker._try_failover_on_error(
            **_failover_kwargs(),
        ):
            events.append(ev)

        # Assert
        mock_worthy.assert_called_once()
        assert events == []

    @patch(
        "src.infrastructure.llm.failover_chain.is_failover_worthy",
    )
    async def test_failover_delegates_when_worthy(
        self,
        mock_worthy: MagicMock,
    ) -> None:
        """When error is failover-worthy, events from
        _attempt_failover are yielded including the sentinel."""
        # Arrange
        mock_worthy.return_value = True
        invoker = _make_invoker(
            failover_chain=MagicMock(name="chain"),
        )

        mock_event = MagicMock(name="domain_event")
        sentinel = _FailoverSuccess()

        async def _fake_attempt(**_kwargs: object):  # type: ignore[no-untyped-def]
            yield mock_event
            yield sentinel

        invoker._attempt_failover = _fake_attempt  # type: ignore[assignment]

        # Act
        events: list[object] = []
        async for ev in invoker._try_failover_on_error(
            **_failover_kwargs(),
        ):
            events.append(ev)

        # Assert
        assert len(events) == 2
        assert events[0] is mock_event
        assert isinstance(events[1], _FailoverSuccess)
