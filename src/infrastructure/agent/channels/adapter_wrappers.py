"""Adapter wrappers bridging transport and domain ChannelAdapter interfaces."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

from src.domain.model.channels.message import (
    MessageContent,
    SenderInfo,
)
from src.infrastructure.agent.channels.channel_adapter import TransportChannelAdapter
from src.infrastructure.agent.channels.channel_message import ChannelMessage


class TransportToDomainAdapter:
    """Wraps a TransportChannelAdapter (infra ABC) to satisfy the domain Protocol."""

    def __init__(self, transport: TransportChannelAdapter) -> None:
        self._transport = transport
        self._connected = False
        self._message_handlers: list[Callable[..., None]] = []
        self._error_handlers: list[Callable[[Exception], None]] = []

    @property
    def id(self) -> str:
        return self._transport.channel_type

    @property
    def name(self) -> str:
        return f"{self._transport.channel_type}:{self._transport.channel_id}"

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        await self._transport.connect()
        self._connected = True

    async def disconnect(self) -> None:
        await self._transport.disconnect()
        self._connected = False

    async def send_message(
        self,
        to: str,
        content: MessageContent,
        reply_to: str | None = None,
    ) -> str:
        text = content.text or ""
        msg_id = str(uuid.uuid4())
        cm = ChannelMessage(
            channel_type=self._transport.channel_type,
            channel_id=to,
            sender_id="agent",
            content=text,
            metadata={"reply_to": reply_to} if reply_to else {},
        )
        await self._transport.send(cm)
        return msg_id

    async def send_text(self, to: str, text: str, reply_to: str | None = None) -> str:
        msg_id = str(uuid.uuid4())
        cm = ChannelMessage(
            channel_type=self._transport.channel_type,
            channel_id=to,
            sender_id="agent",
            content=text,
            metadata={"reply_to": reply_to} if reply_to else {},
        )
        await self._transport.send(cm)
        return msg_id

    def on_message(self, handler: Callable[..., None]) -> Callable[[], None]:
        self._message_handlers.append(handler)

        def _unregister() -> None:
            if handler in self._message_handlers:
                self._message_handlers.remove(handler)

        return _unregister

    def on_error(self, handler: Callable[[Exception], None]) -> Callable[[], None]:
        self._error_handlers.append(handler)

        def _unregister() -> None:
            if handler in self._error_handlers:
                self._error_handlers.remove(handler)

        return _unregister

    async def get_chat_members(self, chat_id: str) -> list[SenderInfo]:
        return []

    async def get_user_info(self, user_id: str) -> SenderInfo | None:
        return None

    async def edit_message(self, message_id: str, content: MessageContent) -> bool:
        return False

    async def delete_message(self, message_id: str) -> bool:
        return False

    async def send_card(
        self,
        to: str,
        card: dict[str, Any],
        reply_to: str | None = None,
    ) -> str:
        msg_id = str(uuid.uuid4())
        cm = ChannelMessage(
            channel_type=self._transport.channel_type,
            channel_id=to,
            sender_id="agent",
            content=json.dumps(card),
            metadata={"type": "card"},
        )
        await self._transport.send(cm)
        return msg_id

    async def health_check(self) -> bool:
        return self._connected

    async def patch_card(self, message_id: str, card_content: str) -> bool:
        return False

    async def send_markdown_card(
        self,
        to: str,
        markdown: str,
        reply_to: str | None = None,
    ) -> str:
        msg_id = str(uuid.uuid4())
        cm = ChannelMessage(
            channel_type=self._transport.channel_type,
            channel_id=to,
            sender_id="agent",
            content=markdown,
            metadata={"type": "markdown_card"},
        )
        await self._transport.send(cm)
        return msg_id
