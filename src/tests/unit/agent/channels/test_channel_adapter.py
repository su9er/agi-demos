"""Tests for the multi-channel message adapter system."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agent.channels.channel_adapter import TransportChannelAdapter
from src.infrastructure.agent.channels.channel_message import ChannelMessage
from src.infrastructure.agent.channels.channel_router import ChannelRouter, RouteResult
from src.infrastructure.agent.channels.channel_types import (
    FEISHU,
    REST_API,
    SLACK,
    WEBHOOK,
    WEBSOCKET,
    ChannelType,
    normalize_channel_type,
)
from src.infrastructure.agent.channels.rest_api_adapter import RestApiChannelAdapter
from src.infrastructure.agent.channels.websocket_adapter import WebSocketChannelAdapter

# =====================================================================
# Channel type constants
# =====================================================================


@pytest.mark.unit
class TestChannelType:
    def test_values(self) -> None:
        assert WEBSOCKET == "websocket"
        assert REST_API == "rest_api"
        assert FEISHU == "feishu"
        assert SLACK == "slack"
        assert WEBHOOK == "webhook"

    def test_is_str(self) -> None:
        assert isinstance(WEBSOCKET, str)
        assert isinstance(REST_API, str)
        assert isinstance(FEISHU, str)

    def test_normalize_channel_type(self) -> None:
        assert normalize_channel_type("WebSocket") == "websocket"
        assert normalize_channel_type("REST-API") == "rest_api"
        assert normalize_channel_type("  feishu  ") == "feishu"

    def test_backwards_compat_alias(self) -> None:
        assert ChannelType is str


# =====================================================================
# ChannelMessage
# =====================================================================


@pytest.mark.unit
class TestChannelMessage:
    def test_create_minimal(self) -> None:
        msg = ChannelMessage(
            channel_type=WEBSOCKET,
            channel_id="sess-1",
            sender_id="user-1",
            content="hello",
        )
        assert msg.channel_type == "websocket"
        assert msg.channel_id == "sess-1"
        assert msg.sender_id == "user-1"
        assert msg.content == "hello"
        assert msg.metadata == {}
        assert msg.conversation_id is None
        assert msg.project_id is None
        assert msg.tenant_id is None

    def test_create_full(self) -> None:
        ts = datetime(2025, 1, 1, tzinfo=UTC)
        msg = ChannelMessage(
            channel_type=REST_API,
            channel_id="req-42",
            sender_id="user-2",
            content="world",
            metadata={"x": "y"},
            timestamp=ts,
            conversation_id="conv-1",
            project_id="proj-1",
            tenant_id="tenant-1",
        )
        assert msg.timestamp == ts
        assert msg.metadata == {"x": "y"}
        assert msg.conversation_id == "conv-1"
        assert msg.project_id == "proj-1"
        assert msg.tenant_id == "tenant-1"

    def test_frozen(self) -> None:
        msg = ChannelMessage(
            channel_type=FEISHU,
            channel_id="c",
            sender_id="s",
            content="x",
        )
        with pytest.raises(AttributeError):
            msg.content = "new"  # type: ignore[misc]

    def test_default_timestamp_is_utc(self) -> None:
        msg = ChannelMessage(
            channel_type=SLACK,
            channel_id="c",
            sender_id="s",
            content="x",
        )
        assert msg.timestamp.tzinfo is not None


# =====================================================================
# ChannelAdapter ABC
# =====================================================================


@pytest.mark.unit
class TestChannelAdapterContract:
    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            TransportChannelAdapter()  # type: ignore[call-arg]


# =====================================================================
# WebSocketChannelAdapter
# =====================================================================


def _make_ws_mock(messages: list[dict[str, Any]]) -> AsyncMock:
    ws = AsyncMock()
    call_count = 0

    async def _recv() -> dict[str, Any]:
        nonlocal call_count
        if call_count < len(messages):
            msg = messages[call_count]
            call_count += 1
            return msg
        raise RuntimeError("connection closed")

    ws.receive_json = AsyncMock(side_effect=_recv)
    ws.send_json = AsyncMock()
    return ws


@pytest.mark.unit
class TestWebSocketChannelAdapter:
    async def test_properties(self) -> None:
        ws = AsyncMock()
        adapter = WebSocketChannelAdapter(ws, user_id="u1", session_id="s1", tenant_id="t1")
        assert adapter.channel_type == "websocket"
        assert adapter.channel_id == "s1"

    async def test_connect_disconnect(self) -> None:
        ws = AsyncMock()
        adapter = WebSocketChannelAdapter(ws, user_id="u1", session_id="s1")
        await adapter.connect()
        assert adapter._connected is True
        await adapter.disconnect()
        assert adapter._connected is False

    async def test_receive_single_message(self) -> None:
        raw = {"message": "hi", "conversation_id": "conv-1", "project_id": "proj-1"}
        ws = _make_ws_mock([raw])
        adapter = WebSocketChannelAdapter(ws, user_id="u1", session_id="s1", tenant_id="t1")
        await adapter.connect()

        received: list[ChannelMessage] = []
        async for msg in adapter.receive():
            received.append(msg)

        assert len(received) == 1
        msg = received[0]
        assert msg.content == "hi"
        assert msg.conversation_id == "conv-1"
        assert msg.project_id == "proj-1"
        assert msg.tenant_id == "t1"
        assert msg.channel_type == "websocket"
        assert msg.sender_id == "u1"

    async def test_receive_multiple_messages(self) -> None:
        ws = _make_ws_mock(
            [
                {"message": "a", "conversation_id": "c1"},
                {"message": "b", "conversation_id": "c1"},
            ]
        )
        adapter = WebSocketChannelAdapter(ws, user_id="u1", session_id="s1")
        await adapter.connect()

        received: list[ChannelMessage] = []
        async for msg in adapter.receive():
            received.append(msg)

        assert len(received) == 2
        assert received[0].content == "a"
        assert received[1].content == "b"

    async def test_receive_not_connected(self) -> None:
        ws = AsyncMock()
        adapter = WebSocketChannelAdapter(ws, user_id="u1", session_id="s1")
        received: list[ChannelMessage] = []
        async for msg in adapter.receive():
            received.append(msg)
        assert received == []

    async def test_send(self) -> None:
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        adapter = WebSocketChannelAdapter(ws, user_id="u1", session_id="s1")
        await adapter.connect()

        msg = ChannelMessage(
            channel_type="websocket",
            channel_id="s1",
            sender_id="agent",
            content="reply",
            conversation_id="conv-1",
        )
        await adapter.send(msg)
        ws.send_json.assert_called_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["content"] == "reply"
        assert payload["conversation_id"] == "conv-1"
        assert payload["type"] == "channel_message"

    async def test_send_when_disconnected_does_not_raise(self) -> None:
        ws = AsyncMock()
        adapter = WebSocketChannelAdapter(ws, user_id="u1", session_id="s1")
        msg = ChannelMessage(
            channel_type="websocket",
            channel_id="s1",
            sender_id="agent",
            content="reply",
        )
        await adapter.send(msg)
        ws.send_json.assert_not_called()

    async def test_metadata_carries_extra_fields(self) -> None:
        raw = {"message": "hi", "conversation_id": "c", "extra_key": "val"}
        ws = _make_ws_mock([raw])
        adapter = WebSocketChannelAdapter(ws, user_id="u1", session_id="s1")
        await adapter.connect()

        received: list[ChannelMessage] = []
        async for msg in adapter.receive():
            received.append(msg)

        assert "extra_key" in received[0].metadata
        assert received[0].metadata["extra_key"] == "val"


# =====================================================================
# RestApiChannelAdapter
# =====================================================================


@pytest.mark.unit
class TestRestApiChannelAdapter:
    async def test_properties(self) -> None:
        adapter = RestApiChannelAdapter(
            request_body={},
            user_id="u1",
            tenant_id="t1",
            request_id="r1",
        )
        assert adapter.channel_type == "rest_api"
        assert adapter.channel_id == "r1"

    async def test_receive_yields_one_message(self) -> None:
        body: dict[str, Any] = {
            "message": "hello",
            "conversation_id": "conv-1",
            "project_id": "proj-1",
        }
        adapter = RestApiChannelAdapter(
            request_body=body,
            user_id="u1",
            tenant_id="t1",
            request_id="r1",
            headers={"x-custom": "h"},
        )
        await adapter.connect()

        received: list[ChannelMessage] = []
        async for msg in adapter.receive():
            received.append(msg)

        assert len(received) == 1
        msg = received[0]
        assert msg.content == "hello"
        assert msg.conversation_id == "conv-1"
        assert msg.project_id == "proj-1"
        assert msg.tenant_id == "t1"
        assert msg.channel_type == "rest_api"
        assert msg.metadata.get("x-custom") == "h"

    async def test_receive_not_connected_yields_nothing(self) -> None:
        adapter = RestApiChannelAdapter(
            request_body={"message": "x"},
            user_id="u1",
            tenant_id="t1",
            request_id="r1",
        )
        received: list[ChannelMessage] = []
        async for msg in adapter.receive():
            received.append(msg)
        assert received == []

    async def test_send_captures_response(self) -> None:
        adapter = RestApiChannelAdapter(
            request_body={},
            user_id="u1",
            tenant_id="t1",
            request_id="r1",
        )
        assert adapter.response is None

        response_msg = ChannelMessage(
            channel_type="rest_api",
            channel_id="r1",
            sender_id="agent",
            content="reply",
            conversation_id="conv-1",
        )
        await adapter.send(response_msg)
        assert adapter.response is response_msg

    async def test_response_as_dict(self) -> None:
        adapter = RestApiChannelAdapter(
            request_body={},
            user_id="u1",
            tenant_id="t1",
            request_id="r1",
        )
        assert "error" in adapter.response_as_dict()

        response_msg = ChannelMessage(
            channel_type="rest_api",
            channel_id="r1",
            sender_id="agent",
            content="ok",
            conversation_id="conv-1",
        )
        await adapter.send(response_msg)
        d = adapter.response_as_dict()
        assert d["content"] == "ok"
        assert d["conversation_id"] == "conv-1"
        assert d["channel_type"] == "rest_api"

    async def test_metadata_includes_extra_body_fields(self) -> None:
        body: dict[str, Any] = {
            "message": "hi",
            "conversation_id": "c",
            "project_id": "p",
            "attachment_ids": "[1,2]",
        }
        adapter = RestApiChannelAdapter(
            request_body=body,
            user_id="u1",
            tenant_id="t1",
            request_id="r1",
        )
        await adapter.connect()

        received: list[ChannelMessage] = []
        async for msg in adapter.receive():
            received.append(msg)

        assert "attachment_ids" in received[0].metadata


# =====================================================================
# ChannelRouter
# =====================================================================


@pytest.mark.unit
class TestChannelRouter:
    def _make_adapter(
        self,
        channel_type: str = "websocket",
        channel_id: str = "ch-1",
    ) -> TransportChannelAdapter:
        adapter = MagicMock(spec=TransportChannelAdapter)
        adapter.channel_type = channel_type
        adapter.channel_id = channel_id
        return adapter

    def test_register_and_get(self) -> None:
        router = ChannelRouter()
        adapter = self._make_adapter()
        router.register_adapter(adapter)
        assert router.get_adapter("websocket", "ch-1") is adapter

    def test_unregister(self) -> None:
        router = ChannelRouter()
        adapter = self._make_adapter()
        router.register_adapter(adapter)
        router.unregister_adapter(adapter)
        assert router.get_adapter("websocket", "ch-1") is None

    def test_registered_adapters_list(self) -> None:
        router = ChannelRouter()
        a1 = self._make_adapter(channel_id="a")
        a2 = self._make_adapter(channel_type="rest_api", channel_id="b")
        router.register_adapter(a1)
        router.register_adapter(a2)
        assert len(router.registered_adapters) == 2

    def test_route_explicit_conversation(self) -> None:
        router = ChannelRouter()
        msg = ChannelMessage(
            channel_type="websocket",
            channel_id="ch-1",
            sender_id="u1",
            content="hi",
            conversation_id="conv-existing",
        )
        result = router.route(msg)
        assert result.message.conversation_id == "conv-existing"
        assert result.is_new_conversation is False
        assert router.conversation_for_channel("ch-1") == "conv-existing"

    def test_route_new_conversation(self) -> None:
        router = ChannelRouter()
        msg = ChannelMessage(
            channel_type="websocket",
            channel_id="ch-new",
            sender_id="u1",
            content="first",
        )
        result = router.route(msg)
        assert result.is_new_conversation is True
        assert result.message.conversation_id is not None
        assert len(result.message.conversation_id) == 36

    def test_route_reuses_existing_mapping(self) -> None:
        router = ChannelRouter()
        msg1 = ChannelMessage(
            channel_type="websocket",
            channel_id="ch-1",
            sender_id="u1",
            content="first",
        )
        r1 = router.route(msg1)

        msg2 = ChannelMessage(
            channel_type="websocket",
            channel_id="ch-1",
            sender_id="u1",
            content="second",
        )
        r2 = router.route(msg2)

        assert r2.is_new_conversation is False
        assert r2.message.conversation_id == r1.message.conversation_id

    def test_route_preserves_fields(self) -> None:
        router = ChannelRouter()
        ts = datetime(2025, 6, 1, tzinfo=UTC)
        msg = ChannelMessage(
            channel_type="feishu",
            channel_id="feishu-chat-1",
            sender_id="u1",
            content="hello",
            metadata={"k": "v"},
            timestamp=ts,
            project_id="proj-1",
            tenant_id="tenant-1",
        )
        result = router.route(msg)
        routed = result.message
        assert routed.channel_type == "feishu"
        assert routed.channel_id == "feishu-chat-1"
        assert routed.sender_id == "u1"
        assert routed.content == "hello"
        assert routed.metadata == {"k": "v"}
        assert routed.timestamp == ts
        assert routed.project_id == "proj-1"
        assert routed.tenant_id == "tenant-1"

    def test_clear_channel(self) -> None:
        router = ChannelRouter()
        msg = ChannelMessage(
            channel_type="websocket",
            channel_id="ch-1",
            sender_id="u1",
            content="x",
        )
        router.route(msg)
        assert router.conversation_for_channel("ch-1") is not None

        router.clear_channel("ch-1")
        assert router.conversation_for_channel("ch-1") is None

    def test_clear_unknown_channel_is_noop(self) -> None:
        router = ChannelRouter()
        router.clear_channel("nonexistent")

    def test_conversation_for_unknown_channel(self) -> None:
        router = ChannelRouter()
        assert router.conversation_for_channel("unknown") is None

    def test_different_channels_get_different_conversations(self) -> None:
        router = ChannelRouter()
        msg_a = ChannelMessage(
            channel_type="websocket",
            channel_id="ch-a",
            sender_id="u1",
            content="a",
        )
        msg_b = ChannelMessage(
            channel_type="feishu",
            channel_id="ch-b",
            sender_id="u2",
            content="b",
        )
        r_a = router.route(msg_a)
        r_b = router.route(msg_b)
        assert r_a.message.conversation_id != r_b.message.conversation_id


# =====================================================================
# RouteResult dataclass
# =====================================================================


@pytest.mark.unit
class TestRouteResult:
    def test_fields(self) -> None:
        msg = ChannelMessage(
            channel_type="websocket",
            channel_id="c",
            sender_id="s",
            content="x",
            conversation_id="conv-1",
        )
        result = RouteResult(message=msg, is_new_conversation=True)
        assert result.message is msg
        assert result.is_new_conversation is True
