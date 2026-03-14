"""Unified channel message representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class ChannelMessage:
    """Immutable, channel-agnostic message exchanged between adapters and the router.

    Attributes:
        channel_type: The transport that originated this message.
        channel_id: Opaque identifier for the specific channel instance
            (e.g. a WebSocket session id, a Feishu chat id).
        sender_id: Authenticated user / bot identifier.
        content: The textual payload.
        metadata: Arbitrary key-value pairs carried along with the message
            (headers, Feishu event fields, etc.).
        timestamp: When the message was created (UTC).
        conversation_id: Optional pre-existing conversation to continue.
        project_id: Optional project scope for multi-tenant routing.
        tenant_id: Optional tenant scope.
    """

    channel_type: str
    channel_id: str
    sender_id: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    conversation_id: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
