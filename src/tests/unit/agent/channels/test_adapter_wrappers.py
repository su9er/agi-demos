"""Tests for TransportToDomainAdapter and DomainToTransportAdapter wrappers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.model.channels.message import (
    MessageContent,
    MessageType,
)
from src.infrastructure.agent.channels.adapter_wrappers import (
    TransportToDomainAdapter,
)
from src.infrastructure.agent.channels.channel_message import ChannelMessage
from src.infrastructure.agent.channels.channel_types import WEBSOCKET


def _make_transport_mock() -> AsyncMock:
    """Create a mock TransportChannelAdapter."""
    mock = AsyncMock()
    mock.channel_type = WEBSOCKET
    mock.channel_id = "sess-1"
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    return mock


@pytest.mark.unit
class TestTransportToDomainAdapter:
    """Tests for wrapping a transport adapter to satisfy the domain Protocol."""

    def test_id_and_name(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)
        assert wrapper.id == WEBSOCKET
        assert wrapper.name == f"{WEBSOCKET}:sess-1"

    def test_connected_property(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)
        assert wrapper.connected is False

    async def test_connect_delegates(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)
        await wrapper.connect()
        transport.connect.assert_awaited_once()
        assert wrapper.connected is True

    async def test_disconnect_delegates(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)
        await wrapper.connect()
        await wrapper.disconnect()
        transport.disconnect.assert_awaited_once()
        assert wrapper.connected is False

    async def test_send_message_delegates_to_send(self) -> None:
        transport = _make_transport_mock()
        transport.send = AsyncMock()
        wrapper = TransportToDomainAdapter(transport)

        content = MessageContent(type=MessageType.TEXT, text="hello")
        result = await wrapper.send_message(to="chat-1", content=content)

        transport.send.assert_awaited_once()
        sent_msg: ChannelMessage = transport.send.call_args[0][0]
        assert sent_msg.content == "hello"
        assert sent_msg.channel_id == "chat-1"
        # Returns a placeholder message ID
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_send_text_delegates(self) -> None:
        transport = _make_transport_mock()
        transport.send = AsyncMock()
        wrapper = TransportToDomainAdapter(transport)

        result = await wrapper.send_text(to="chat-1", text="hi there")

        transport.send.assert_awaited_once()
        sent_msg: ChannelMessage = transport.send.call_args[0][0]
        assert sent_msg.content == "hi there"
        assert isinstance(result, str)

    def test_on_message_returns_unregister(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)

        handler = MagicMock()
        unregister = wrapper.on_message(handler)
        assert callable(unregister)

    def test_on_error_returns_unregister(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)

        handler = MagicMock()
        unregister = wrapper.on_error(handler)
        assert callable(unregister)

    async def test_health_check_returns_connected_state(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)
        assert await wrapper.health_check() is False

        await wrapper.connect()
        assert await wrapper.health_check() is True

    async def test_get_chat_members_returns_empty(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)
        members = await wrapper.get_chat_members("chat-1")
        assert members == []

    async def test_get_user_info_returns_none(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)
        info = await wrapper.get_user_info("user-1")
        assert info is None

    async def test_edit_message_returns_false(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)
        content = MessageContent(type=MessageType.TEXT, text="edited")
        result = await wrapper.edit_message("msg-1", content)
        assert result is False

    async def test_delete_message_returns_false(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)
        result = await wrapper.delete_message("msg-1")
        assert result is False

    async def test_send_card_delegates_to_send(self) -> None:
        transport = _make_transport_mock()
        transport.send = AsyncMock()
        wrapper = TransportToDomainAdapter(transport)

        card = {"type": "interactive", "elements": []}
        result = await wrapper.send_card(to="chat-1", card=card)
        transport.send.assert_awaited_once()
        assert isinstance(result, str)

    async def test_patch_card_returns_false(self) -> None:
        transport = _make_transport_mock()
        wrapper = TransportToDomainAdapter(transport)
        result = await wrapper.patch_card("msg-1", '{"elements": []}')
        assert result is False

    async def test_send_markdown_card_delegates(self) -> None:
        transport = _make_transport_mock()
        transport.send = AsyncMock()
        wrapper = TransportToDomainAdapter(transport)

        result = await wrapper.send_markdown_card(to="chat-1", markdown="# Hello")
        transport.send.assert_awaited_once()
        assert isinstance(result, str)
