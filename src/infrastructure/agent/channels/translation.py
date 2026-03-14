"""ChannelMessage <-> domain Message translation utilities."""

from __future__ import annotations

import uuid

from src.domain.model.channels.message import (
    ChatType,
    Message,
    MessageContent,
    MessageType,
    SenderInfo,
)
from src.infrastructure.agent.channels.channel_message import ChannelMessage


def channel_message_to_domain(cm: ChannelMessage) -> Message:
    chat_type = ChatType.P2P
    if cm.metadata.get("chat_type") == "group":
        chat_type = ChatType.GROUP

    return Message(
        id=str(uuid.uuid4()),
        channel=cm.channel_type,
        chat_type=chat_type,
        chat_id=cm.channel_id,
        sender=SenderInfo(id=cm.sender_id),
        content=MessageContent(type=MessageType.TEXT, text=cm.content),
        project_id=cm.project_id,
        created_at=cm.timestamp,
        raw_data=dict(cm.metadata) if cm.metadata else None,
    )


def domain_to_channel_message(
    msg: Message,
    *,
    tenant_id: str | None = None,
) -> ChannelMessage:
    text = msg.content.text or ""

    metadata: dict[str, str] = {}
    metadata["chat_type"] = msg.chat_type.value
    if msg.sender.name:
        metadata["sender_name"] = msg.sender.name

    conversation_id: str | None = None
    if msg.raw_data and "conversation_id" in msg.raw_data:
        conversation_id = str(msg.raw_data["conversation_id"])

    return ChannelMessage(
        channel_type=msg.channel,
        channel_id=msg.chat_id,
        sender_id=msg.sender.id,
        content=text,
        metadata=metadata,
        timestamp=msg.created_at,
        conversation_id=conversation_id,
        project_id=msg.project_id,
        tenant_id=tenant_id,
    )
