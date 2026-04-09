"""Unit tests for AgentService.connect_chat_stream cursor/replay behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.services.agent_service import AgentService


class _TestAgentService(AgentService):
    async def get_available_tools(self):
        return []

    async def get_conversation_context(self, conversation_id: str):
        return []


def _build_service() -> _TestAgentService:
    conversation_repo = AsyncMock()
    execution_repo = AsyncMock()
    graph_service = AsyncMock()
    llm = AsyncMock()
    neo4j_client = AsyncMock()
    agent_event_repo = AsyncMock()
    service = _TestAgentService(
        conversation_repository=conversation_repo,
        execution_repository=execution_repo,
        graph_service=graph_service,
        llm=llm,
        neo4j_client=neo4j_client,
        agent_execution_event_repository=agent_event_repo,
        redis_client=None,
    )
    service._event_bus = SimpleNamespace(stream_read=AsyncMock())
    return service


@pytest.mark.unit
@pytest.mark.asyncio
async def test_connect_chat_stream_skips_db_replay_when_disabled() -> None:
    service = _build_service()
    service._replay_db_events = AsyncMock(
        return_value=(
            [],
            0,
            0,
            False,
        )
    )

    async def _stream_read(*_args, **_kwargs):
        yield {
            "id": "1-0",
            "data": {
                "type": "text_delta",
                "event_time_us": 10,
                "event_counter": 1,
                "data": {"message_id": "m1", "delta": "hello"},
            },
        }
        yield {
            "id": "2-0",
            "data": {
                "type": "complete",
                "event_time_us": 11,
                "event_counter": 2,
                "data": {"message_id": "m1", "content": "done"},
            },
        }

    service._event_bus.stream_read = _stream_read
    service._read_delayed_events = AsyncMock(return_value=[])
    service._handle_title_generation = AsyncMock()

    events = []
    async for event in service.connect_chat_stream(
        conversation_id="conv-1",
        message_id="m1",
        replay_from_db=False,
    ):
        events.append(event)

    service._replay_db_events.assert_not_awaited()
    assert [event["type"] for event in events] == ["text_delta", "complete"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_connect_chat_stream_honors_cursor_without_db_replay() -> None:
    service = _build_service()
    service._replay_db_events = AsyncMock(
        return_value=(
            [],
            0,
            0,
            False,
        )
    )

    async def _stream_read(*_args, **_kwargs):
        # Already seen by cursor -> should be skipped
        yield {
            "id": "1-0",
            "data": {
                "type": "text_delta",
                "event_time_us": 20,
                "event_counter": 3,
                "data": {"message_id": "m1", "delta": "old"},
            },
        }
        # New event -> should pass
        yield {
            "id": "2-0",
            "data": {
                "type": "text_delta",
                "event_time_us": 20,
                "event_counter": 4,
                "data": {"message_id": "m1", "delta": "new"},
            },
        }
        yield {
            "id": "3-0",
            "data": {
                "type": "complete",
                "event_time_us": 21,
                "event_counter": 1,
                "data": {"message_id": "m1", "content": "done"},
            },
        }

    service._event_bus.stream_read = _stream_read
    service._read_delayed_events = AsyncMock(return_value=[])
    service._handle_title_generation = AsyncMock()

    events = []
    async for event in service.connect_chat_stream(
        conversation_id="conv-1",
        message_id="m1",
        replay_from_db=False,
        from_time_us=20,
        from_counter=3,
    ):
        events.append(event)

    assert [event["type"] for event in events] == ["text_delta", "complete"]
    assert events[0]["data"]["delta"] == "new"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_connect_chat_stream_keeps_higher_cursor_than_replay() -> None:
    service = _build_service()

    async def _stream_read(*_args, **_kwargs):
        # lower/equal than caller cursor(40,2) -> skip
        yield {
            "id": "1-0",
            "data": {
                "type": "text_delta",
                "event_time_us": 40,
                "event_counter": 2,
                "data": {"message_id": "m1", "delta": "skip"},
            },
        }
        # greater than caller cursor -> yield
        yield {
            "id": "2-0",
            "data": {
                "type": "text_delta",
                "event_time_us": 40,
                "event_counter": 3,
                "data": {"message_id": "m1", "delta": "keep"},
            },
        }
        yield {
            "id": "3-0",
            "data": {
                "type": "complete",
                "event_time_us": 41,
                "event_counter": 1,
                "data": {"message_id": "m1", "content": "done"},
            },
        }

    # replay still enabled, but caller cursor should remain authoritative if greater
    service._replay_db_events = AsyncMock(return_value=([], 31, 1, False))
    service._event_bus.stream_read = _stream_read
    service._read_delayed_events = AsyncMock(return_value=[])
    service._handle_title_generation = AsyncMock()

    events = []
    async for event in service.connect_chat_stream(
        conversation_id="conv-1",
        message_id="m1",
        replay_from_db=True,
        from_time_us=40,
        from_counter=2,
    ):
        events.append(event)

    assert [event["type"] for event in events] == ["text_delta", "complete"]
    assert events[0]["data"]["delta"] == "keep"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_replay_db_events_repairs_malformed_task_list_updated_payload() -> None:
    service = _build_service()
    created_at = datetime.now(UTC)
    task_snapshot = [
        {
            "id": "task-1",
            "conversation_id": "conv-1",
            "content": "Repair replay payload",
            "status": "pending",
            "priority": "medium",
            "order_index": 0,
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
    ]
    service._agent_execution_event_repo.get_events_by_message.return_value = [
        SimpleNamespace(
            event_type="task_list_updated",
            event_data={},
            created_at=created_at,
            event_time_us=55,
            event_counter=2,
        )
    ]
    service._load_task_snapshot = AsyncMock(return_value=task_snapshot)

    events, last_event_time_us, last_event_counter, saw_complete = await service._replay_db_events(
        "conv-1",
        "msg-1",
    )

    assert events == [
        {
            "type": "task_list_updated",
            "data": {"conversation_id": "conv-1", "tasks": task_snapshot},
            "timestamp": created_at.isoformat(),
            "event_time_us": 55,
            "event_counter": 2,
        }
    ]
    assert last_event_time_us == 55
    assert last_event_counter == 2
    assert saw_complete is False
    service._agent_execution_event_repo.get_events_by_message.assert_awaited_once_with(
        conversation_id="conv-1",
        message_id="msg-1",
    )
    service._load_task_snapshot.assert_awaited_once_with("conv-1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_replay_db_events_replaces_malformed_task_updated_with_snapshot() -> None:
    service = _build_service()
    created_at = datetime.now(UTC)
    task_snapshot = [
        {
            "id": "task-1",
            "conversation_id": "conv-1",
            "content": "Recovered task state",
            "status": "in_progress",
            "priority": "medium",
            "order_index": 0,
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
    ]
    service._agent_execution_event_repo.get_events_by_message.return_value = [
        SimpleNamespace(
            event_type="task_updated",
            event_data={"conversation_id": "conv-1"},
            created_at=created_at,
            event_time_us=89,
            event_counter=4,
        )
    ]
    service._load_task_snapshot = AsyncMock(return_value=task_snapshot)

    events, last_event_time_us, last_event_counter, saw_complete = await service._replay_db_events(
        "conv-1",
        "msg-1",
    )

    assert events == [
        {
            "type": "task_list_updated",
            "data": {"conversation_id": "conv-1", "tasks": task_snapshot},
            "timestamp": created_at.isoformat(),
            "event_time_us": 89,
            "event_counter": 4,
        }
    ]
    assert last_event_time_us == 89
    assert last_event_counter == 4
    assert saw_complete is False
    service._agent_execution_event_repo.get_events_by_message.assert_awaited_once_with(
        conversation_id="conv-1",
        message_id="msg-1",
    )
    service._load_task_snapshot.assert_awaited_once_with("conv-1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_replay_db_events_repairs_task_update_for_wrong_conversation() -> None:
    service = _build_service()
    created_at = datetime.now(UTC)
    task_snapshot = [
        {
            "id": "task-2",
            "conversation_id": "conv-1",
            "content": "Correct conversation snapshot",
            "status": "completed",
            "priority": "medium",
            "order_index": 1,
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
    ]
    service._agent_execution_event_repo.get_events_by_message.return_value = [
        SimpleNamespace(
            event_type="task_updated",
            event_data={
                "conversation_id": "conv-other",
                "task_id": "task-2",
                "status": "completed",
            },
            created_at=created_at,
            event_time_us=144,
            event_counter=5,
        )
    ]
    service._load_task_snapshot = AsyncMock(return_value=task_snapshot)

    events, last_event_time_us, last_event_counter, saw_complete = await service._replay_db_events(
        "conv-1",
        "msg-1",
    )

    assert events == [
        {
            "type": "task_list_updated",
            "data": {"conversation_id": "conv-1", "tasks": task_snapshot},
            "timestamp": created_at.isoformat(),
            "event_time_us": 144,
            "event_counter": 5,
        }
    ]
    assert last_event_time_us == 144
    assert last_event_counter == 5
    assert saw_complete is False
    service._agent_execution_event_repo.get_events_by_message.assert_awaited_once_with(
        conversation_id="conv-1",
        message_id="msg-1",
    )
    service._load_task_snapshot.assert_awaited_once_with("conv-1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_first_user_message_scopes_event_lookup_to_conversation() -> None:
    service = _build_service()
    service._agent_execution_event_repo.get_events_by_message.return_value = [
        SimpleNamespace(
            event_type="user_message",
            event_data={"content": "hello"},
        )
    ]

    content = await service._extract_first_user_message("conv-1", "msg-1")

    assert content == "hello"
    service._agent_execution_event_repo.get_events_by_message.assert_awaited_once_with(
        conversation_id="conv-1",
        message_id="msg-1",
    )
