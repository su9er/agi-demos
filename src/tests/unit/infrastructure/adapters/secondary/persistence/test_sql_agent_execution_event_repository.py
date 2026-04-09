"""Tests for SqlAgentExecutionEventRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.adapters.secondary.persistence.sql_agent_execution_event_repository import (
    SqlAgentExecutionEventRepository,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_events_by_message_ids_filters_by_conversation_and_message_ids() -> None:
    """Batch lookups must scope by conversation_id to avoid cross-conversation leaks."""
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=result)

    repo = SqlAgentExecutionEventRepository(session)

    await repo.get_events_by_message_ids("conv-a", {"shared-msg"})

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()

    assert "agent_execution_events.conversation_id = :conversation_id_1" in str(compiled)
    assert "agent_execution_events.message_id IN" in str(compiled)
    assert compiled.params["conversation_id_1"] == "conv-a"
    assert compiled.params["message_id_1"] == ["shared-msg"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_events_by_message_filters_by_conversation_and_message_id() -> None:
    """Single-message lookups must scope by conversation_id to avoid leaks."""
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=result)

    repo = SqlAgentExecutionEventRepository(session)

    await repo.get_events_by_message("conv-a", "shared-msg")

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()

    assert "agent_execution_events.conversation_id = :conversation_id_1" in str(compiled)
    assert "agent_execution_events.message_id = :message_id_1" in str(compiled)
    assert compiled.params["conversation_id_1"] == "conv-a"
    assert compiled.params["message_id_1"] == "shared-msg"
