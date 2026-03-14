"""Channel router -- dispatches incoming channel messages to agent conversations.

The router maintains a registry of :class:`TransportChannelAdapter` instances
and a mapping from ``channel_id`` to ``conversation_id`` so that follow-up
messages on the same channel automatically continue the correct
conversation.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from src.infrastructure.agent.channels.channel_adapter import TransportChannelAdapter
from src.infrastructure.agent.channels.channel_message import ChannelMessage

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """Outcome of routing a single :class:`ChannelMessage`.

    Attributes:
        message: The (possibly enriched) message with ``conversation_id`` set.
        is_new_conversation: ``True`` when a brand-new conversation was allocated.
    """

    message: ChannelMessage
    is_new_conversation: bool


class ChannelRouter:
    """Routes :class:`ChannelMessage` instances to agent conversations.

    Responsibilities:

    * Maintain a registry of adapters keyed by ``(channel_type, channel_id)``.
    * Map ``channel_id`` -> ``conversation_id`` so repeat messages on the
      same channel continue the same conversation.
    * Allocate a new ``conversation_id`` when a message arrives on a
      previously-unseen channel (or when the message explicitly requests
      a new conversation by leaving ``conversation_id`` empty).

    The router is deliberately **stateless with respect to persistence** --
    it keeps an in-memory mapping only.  A production deployment would
    back this with Redis or a database table.
    """

    def __init__(self) -> None:
        # (channel_type, channel_id) -> ChannelAdapter
        self._adapters: dict[tuple[str, str], TransportChannelAdapter] = {}
        # channel_id -> conversation_id
        self._channel_to_conversation: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Adapter registry
    # ------------------------------------------------------------------

    def register_adapter(self, adapter: TransportChannelAdapter) -> None:
        """Register an adapter so the router can later look it up."""
        key = (adapter.channel_type, adapter.channel_id)
        self._adapters[key] = adapter
        logger.debug("Registered adapter %s/%s", adapter.channel_type, adapter.channel_id)

    def unregister_adapter(self, adapter: TransportChannelAdapter) -> None:
        """Remove a previously registered adapter."""
        key = (adapter.channel_type, adapter.channel_id)
        self._adapters.pop(key, None)
        logger.debug("Unregistered adapter %s/%s", adapter.channel_type, adapter.channel_id)

    def get_adapter(self, channel_type: str, channel_id: str) -> TransportChannelAdapter | None:
        """Look up a registered adapter by type and id."""
        return self._adapters.get((channel_type, channel_id))

    @property
    def registered_adapters(self) -> list[TransportChannelAdapter]:
        """Return a snapshot of all currently registered adapters."""
        return list(self._adapters.values())

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route(self, message: ChannelMessage) -> RouteResult:
        """Resolve the ``conversation_id`` for *message* and return a :class:`RouteResult`.

        Rules:

        1. If the message already carries a ``conversation_id``, honour it and
           update the mapping.
        2. If the ``channel_id`` was seen before, reuse the mapped
           ``conversation_id``.
        3. Otherwise allocate a new UUID as ``conversation_id``.
        """
        is_new = False
        conversation_id = message.conversation_id

        if conversation_id:
            # Explicit conversation -- update mapping.
            self._channel_to_conversation[message.channel_id] = conversation_id
        elif message.channel_id in self._channel_to_conversation:
            conversation_id = self._channel_to_conversation[message.channel_id]
        else:
            conversation_id = str(uuid.uuid4())
            self._channel_to_conversation[message.channel_id] = conversation_id
            is_new = True
            logger.info(
                "New conversation %s for channel %s/%s",
                conversation_id,
                message.channel_type,
                message.channel_id,
            )

        # Build an enriched copy with the resolved conversation_id.
        routed = ChannelMessage(
            channel_type=message.channel_type,
            channel_id=message.channel_id,
            sender_id=message.sender_id,
            content=message.content,
            metadata=message.metadata,
            timestamp=message.timestamp,
            conversation_id=conversation_id,
            project_id=message.project_id,
            tenant_id=message.tenant_id,
        )
        return RouteResult(message=routed, is_new_conversation=is_new)

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def conversation_for_channel(self, channel_id: str) -> str | None:
        """Return the conversation_id currently mapped to *channel_id*, if any."""
        return self._channel_to_conversation.get(channel_id)

    def clear_channel(self, channel_id: str) -> None:
        """Remove the channel -> conversation mapping (e.g. on disconnect)."""
        self._channel_to_conversation.pop(channel_id, None)

    def set_channel_mapping(self, channel_id: str, conversation_id: str) -> None:
        """Explicitly map *channel_id* to *conversation_id*."""
        self._channel_to_conversation[channel_id] = conversation_id
