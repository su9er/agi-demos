"""REST API channel adapter.

Wraps a single REST request/response cycle as a :class:`ChannelAdapter`.
Unlike the WebSocket adapter which is long-lived, the REST adapter
represents a **one-shot** message exchange: one ``receive`` yields exactly
one :class:`ChannelMessage`, and one ``send`` captures the response.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from src.infrastructure.agent.channels.channel_adapter import ChannelAdapter
from src.infrastructure.agent.channels.channel_message import ChannelMessage
from src.infrastructure.agent.channels.channel_types import ChannelType

logger = logging.getLogger(__name__)


class RestApiChannelAdapter(ChannelAdapter):
    """Adapter that models a REST API request as a channel message.

    Parameters:
        request_body: The parsed JSON body of the incoming HTTP request.
        user_id: Authenticated user identifier.
        tenant_id: Tenant scope.
        request_id: Unique identifier for this HTTP request (used as ``channel_id``).
        headers: Optional HTTP headers to carry as metadata.
    """

    def __init__(
        self,
        request_body: dict[str, Any],
        user_id: str,
        tenant_id: str,
        request_id: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._request_body = request_body
        self._user_id = user_id
        self._tenant_id = tenant_id
        self._request_id = request_id
        self._headers = headers or {}
        self._connected = False
        self._response: ChannelMessage | None = None

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.REST_API

    @property
    def channel_id(self) -> str:
        return self._request_id

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        self._connected = True
        logger.debug("RestApiChannelAdapter connected (request=%s)", self._request_id)

    async def disconnect(self) -> None:
        self._connected = False
        logger.debug("RestApiChannelAdapter disconnected (request=%s)", self._request_id)

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def receive(self) -> AsyncIterator[ChannelMessage]:
        """Yield exactly one :class:`ChannelMessage` from the REST body."""
        if not self._connected:
            return

        metadata = dict(self._headers)
        # Carry non-core fields from the request body as metadata.
        for key, value in self._request_body.items():
            if key not in {"message", "conversation_id", "project_id"}:
                metadata[key] = str(value)

        yield ChannelMessage(
            channel_type=ChannelType.REST_API,
            channel_id=self._request_id,
            sender_id=self._user_id,
            content=str(self._request_body.get("message", "")),
            metadata=metadata,
            timestamp=datetime.now(UTC),
            conversation_id=self._request_body.get("conversation_id"),
            project_id=self._request_body.get("project_id"),
            tenant_id=self._tenant_id,
        )

    async def send(self, message: ChannelMessage) -> None:
        """Capture the response for later retrieval by the endpoint handler."""
        self._response = message
        logger.debug(
            "RestApiChannelAdapter captured response (request=%s)",
            self._request_id,
        )

    # ------------------------------------------------------------------
    # REST-specific helpers
    # ------------------------------------------------------------------

    @property
    def response(self) -> ChannelMessage | None:
        """The captured response message, if any."""
        return self._response

    def response_as_dict(self) -> dict[str, Any]:
        """Serialise the captured response to a plain dict for JSON output."""
        if self._response is None:
            return {"error": "No response captured"}
        return {
            "channel_type": self._response.channel_type.value,
            "content": self._response.content,
            "sender_id": self._response.sender_id,
            "conversation_id": self._response.conversation_id,
            "timestamp": self._response.timestamp.isoformat(),
            "metadata": self._response.metadata,
        }
