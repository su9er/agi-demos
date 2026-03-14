"""Tests for ChannelMessage <-> domain Message translation utilities."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.domain.model.channels.message import (
    ChatType,
    Message,
    MessageContent,
    MessageType,
    SenderInfo,
)
from src.infrastructure.agent.channels.channel_message import ChannelMessage
from src.infrastructure.agent.channels.channel_types import FEISHU, WEBSOCKET
from src.infrastructure.agent.channels.translation import (
    channel_message_to_domain,
    domain_to_channel_message,
)


@pytest.mark.unit
class TestChannelMessageToDomain:
    """Tests for channel_message_to_domain conversion."""

    def test_basic_text_conversion(self) -> None:
        ts = datetime(2025, 7, 1, 12, 0, 0, tzinfo=UTC)
        cm = ChannelMessage(
            channel_type=WEBSOCKET,
            channel_id="sess-1",
            sender_id="user-42",
            content="Hello world",
            metadata={"extra": "val"},
            timestamp=ts,
            conversation_id="conv-1",
            project_id="proj-1",
            tenant_id="tenant-1",
        )

        msg = channel_message_to_domain(cm)

        assert isinstance(msg, Message)
        assert msg.channel == WEBSOCKET
        assert msg.chat_id == "sess-1"
        assert msg.sender.id == "user-42"
        assert msg.content.type == MessageType.TEXT
        assert msg.content.text == "Hello world"
        assert msg.project_id == "proj-1"
        assert msg.created_at == ts

    def test_empty_content(self) -> None:
        cm = ChannelMessage(
            channel_type=FEISHU,
            channel_id="chat-1",
            sender_id="user-1",
            content="",
        )
        msg = channel_message_to_domain(cm)
        assert msg.content.text == ""
        assert msg.content.type == MessageType.TEXT

    def test_chat_type_defaults_to_p2p(self) -> None:
        cm = ChannelMessage(
            channel_type=WEBSOCKET,
            channel_id="c",
            sender_id="s",
            content="x",
        )
        msg = channel_message_to_domain(cm)
        assert msg.chat_type == ChatType.P2P

    def test_group_chat_type_from_metadata(self) -> None:
        cm = ChannelMessage(
            channel_type=FEISHU,
            channel_id="c",
            sender_id="s",
            content="x",
            metadata={"chat_type": "group"},
        )
        msg = channel_message_to_domain(cm)
        assert msg.chat_type == ChatType.GROUP

    def test_raw_data_preserves_metadata(self) -> None:
        cm = ChannelMessage(
            channel_type=WEBSOCKET,
            channel_id="c",
            sender_id="s",
            content="x",
            metadata={"key": "val"},
        )
        msg = channel_message_to_domain(cm)
        assert msg.raw_data is not None
        assert msg.raw_data["key"] == "val"


@pytest.mark.unit
class TestDomainToChannelMessage:
    """Tests for domain_to_channel_message conversion."""

    def test_basic_conversion(self) -> None:
        ts = datetime(2025, 7, 1, 12, 0, 0, tzinfo=UTC)
        msg = Message(
            channel="websocket",
            chat_type=ChatType.P2P,
            chat_id="sess-1",
            sender=SenderInfo(id="user-42", name="Alice"),
            content=MessageContent(type=MessageType.TEXT, text="Hello"),
            project_id="proj-1",
            created_at=ts,
        )

        cm = domain_to_channel_message(msg, tenant_id="tenant-1")

        assert isinstance(cm, ChannelMessage)
        assert cm.channel_type == "websocket"
        assert cm.channel_id == "sess-1"
        assert cm.sender_id == "user-42"
        assert cm.content == "Hello"
        assert cm.project_id == "proj-1"
        assert cm.tenant_id == "tenant-1"
        assert cm.timestamp == ts

    def test_none_text_yields_empty_string(self) -> None:
        msg = Message(
            channel="feishu",
            chat_type=ChatType.P2P,
            chat_id="c",
            sender=SenderInfo(id="s"),
            content=MessageContent(type=MessageType.IMAGE, image_key="img-1"),
        )
        cm = domain_to_channel_message(msg)
        assert cm.content == ""

    def test_conversation_id_from_raw_data(self) -> None:
        msg = Message(
            channel="websocket",
            chat_type=ChatType.P2P,
            chat_id="c",
            sender=SenderInfo(id="s"),
            content=MessageContent(type=MessageType.TEXT, text="hi"),
            raw_data={"conversation_id": "conv-99"},
        )
        cm = domain_to_channel_message(msg)
        assert cm.conversation_id == "conv-99"

    def test_metadata_includes_chat_type(self) -> None:
        msg = Message(
            channel="feishu",
            chat_type=ChatType.GROUP,
            chat_id="c",
            sender=SenderInfo(id="s"),
            content=MessageContent(type=MessageType.TEXT, text="hi"),
        )
        cm = domain_to_channel_message(msg)
        assert cm.metadata["chat_type"] == "group"

    def test_metadata_includes_sender_name(self) -> None:
        msg = Message(
            channel="websocket",
            chat_type=ChatType.P2P,
            chat_id="c",
            sender=SenderInfo(id="s", name="Bob"),
            content=MessageContent(type=MessageType.TEXT, text="hi"),
        )
        cm = domain_to_channel_message(msg)
        assert cm.metadata["sender_name"] == "Bob"
