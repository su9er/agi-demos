"""WebSocket channel adapter.

Wraps the existing WebSocket infrastructure to expose it through the
unified :class:`ChannelAdapter` interface.  This adapter does **not**
modify the underlying ``ConnectionManager`` or ``MessageRouter`` -- it
acts as a thin translation layer.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Protocol

from src.infrastructure.agent.channels.channel_adapter import ChannelAdapter
from src.infrastructure.agent.channels.channel_message import ChannelMessage
from src.infrastructure.agent.channels.channel_types import ChannelType

logger = logging.getLogger(__name__)


class _WebSocketLike(Protocol):
    """Minimal protocol for WebSocket-like objects."""

    async def receive_json(self) -> dict[str, Any]: ...

    async def send_json(self, data: dict[str, Any]) -> None: ...



class WebSocketChannelAdapter(ChannelAdapter):
    """Adapter that bridges a raw WebSocket connection to :class:`ChannelMessage`.

    Parameters:
        websocket: A ``fastapi.WebSocket`` (or any object implementing
            ``receive_json`` / ``send_json``).
        user_id: Authenticated user identifier.
        session_id: WebSocket session identifier.
        tenant_id: Tenant scope (may be empty string when unknown).
    """

    def __init__(
        self,
        websocket: _WebSocketLike,
        user_id: str,
        session_id: str,
        tenant_id: str = "",
    ) -> None:
        self._websocket = websocket
        self._user_id = user_id
        self._session_id = session_id
        self._tenant_id = tenant_id
        self._connected = False

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WEBSOCKET

    @property
    def channel_id(self) -> str:
        return self._session_id

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Mark the adapter as connected.

        The actual ``websocket.accept()`` is expected to have been done
        by the existing ``ConnectionManager``.  This method only flips
        the internal flag so that :meth:`receive` starts yielding.
        """
        self._connected = True
        logger.debug("WebSocketChannelAdapter connected (session=%s)", self._session_id)

    async def disconnect(self) -> None:
        self._connected = False
        logger.debug("WebSocketChannelAdapter disconnected (session=%s)", self._session_id)

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def receive(self) -> AsyncIterator[ChannelMessage]:
        """Yield :class:`ChannelMessage` objects from the WebSocket.

        Each JSON frame is expected to contain at least ``message`` and
        ``conversation_id`` keys (mirroring the existing ``send_message``
        handler payload).
        """
        while self._connected:
            try:
                raw: dict[str, Any] = await self._websocket.receive_json()
            except Exception:
                logger.debug("WebSocket receive ended (session=%s)", self._session_id)
                self._connected = False
                break

            yield ChannelMessage(
                channel_type=ChannelType.WEBSOCKET,
                channel_id=self._session_id,
                sender_id=self._user_id,
                content=str(raw.get("message", "")),
                metadata={k: str(v) for k, v in raw.items() if k != "message"},
                timestamp=datetime.now(UTC),
                conversation_id=raw.get("conversation_id"),
                project_id=raw.get("project_id"),
                tenant_id=self._tenant_id,
            )

    async def send(self, message: ChannelMessage) -> None:
        """Push a :class:`ChannelMessage` back over the WebSocket as JSON."""
        if not self._connected:
            logger.warning(
                "Attempted send on disconnected WebSocket (session=%s)",
                self._session_id,
            )
            return

        payload: dict[str, Any] = {
            "type": "channel_message",
            "channel_type": message.channel_type.value,
            "content": message.content,
            "sender_id": message.sender_id,
            "timestamp": message.timestamp.isoformat(),
            "metadata": message.metadata,
        }
        if message.conversation_id:
            payload["conversation_id"] = message.conversation_id

        await self._websocket.send_json(payload)
