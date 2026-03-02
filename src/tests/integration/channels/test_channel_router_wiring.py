"""Integration tests for ChannelMessageRouter <-> ChannelRouter wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.channels.channel_message_router import (
    ChannelMessageRouter,
)
from src.domain.model.channels.message import (
    ChatType,
    Message,
    MessageContent,
    MessageType,
    SenderInfo,
)


def _make_message(
    *,
    project_id: str = "proj-1",
    channel: str = "feishu",
    chat_id: str = "chat-1",
    sender_id: str = "user-1",
    channel_config_id: str = "cfg-1",
) -> Message:
    """Build a minimal Message with routing metadata."""
    return Message(
        channel=channel,
        chat_type=ChatType.GROUP,
        chat_id=chat_id,
        sender=SenderInfo(id=sender_id, name="Test"),
        content=MessageContent(type=MessageType.TEXT, text="hello"),
        project_id=project_id,
        raw_data={
            "_routing": {"channel_config_id": channel_config_id},
        },
    )


@pytest.mark.integration
class TestChannelRouterWiring:
    """Verify ChannelMessageRouter delegates to infra ChannelRouter."""

    async def test_infra_router_checked_after_cache_miss(self) -> None:
        """When in-memory cache misses, the infra router is consulted."""
        # Arrange
        infra_router = MagicMock()
        infra_router.conversation_for_channel.return_value = "conv-123"

        router = ChannelMessageRouter(
            infra_channel_router=infra_router,
        )
        message = _make_message()

        # Act
        result = await router._get_or_create_conversation(message)

        # Assert
        infra_router.conversation_for_channel.assert_called_once()
        assert result == "conv-123"

    async def test_infra_router_skipped_when_cache_hit(self) -> None:
        """When in-memory cache has the key, infra router is not called."""
        # Arrange
        infra_router = MagicMock()
        infra_router.conversation_for_channel.return_value = "conv-456"

        router = ChannelMessageRouter(
            infra_channel_router=infra_router,
        )
        message = _make_message()

        # Pre-populate cache using the same session key the router builds
        session_key = router._build_session_key(message, "cfg-1")
        router._chat_to_conversation[session_key] = "conv-cached"

        # Act
        result = await router._get_or_create_conversation(message)

        # Assert
        infra_router.conversation_for_channel.assert_not_called()
        assert result == "conv-cached"

    async def test_set_channel_mapping_on_db_create(self) -> None:
        """After DB creates a conversation, infra router mapping is set."""
        # Arrange
        infra_router = MagicMock()
        infra_router.conversation_for_channel.return_value = None

        router = ChannelMessageRouter(
            infra_channel_router=infra_router,
        )
        message = _make_message()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        db_patch = patch(
            "src.infrastructure.adapters.secondary.persistence"
            ".database.async_session_factory",
            return_value=mock_session,
        )
        find_patch = patch.object(
            router,
            "_find_or_create_conversation_db",
            new_callable=AsyncMock,
            return_value="conv-new",
        )

        # Act
        with db_patch, find_patch:
            result = await router._get_or_create_conversation(message)

        # Assert
        assert result == "conv-new"
        infra_router.set_channel_mapping.assert_called_once()
        call_args = infra_router.set_channel_mapping.call_args
        assert call_args[0][1] == "conv-new"

    async def test_no_infra_router_falls_through_to_db(self) -> None:
        """When infra_channel_router is None, DB path is taken."""
        # Arrange
        router = ChannelMessageRouter(infra_channel_router=None)
        message = _make_message()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        db_patch = patch(
            "src.infrastructure.adapters.secondary.persistence"
            ".database.async_session_factory",
            return_value=mock_session,
        )
        find_patch = patch.object(
            router,
            "_find_or_create_conversation_db",
            new_callable=AsyncMock,
            return_value="conv-db",
        )

        # Act
        with db_patch, find_patch:
            result = await router._get_or_create_conversation(message)

        # Assert
        assert result == "conv-db"
