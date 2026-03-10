"""High-level adapter for Volcengine RTC AI voice/video chat sessions.

Wraps :class:`VolcengineVoiceChatAPI` with application-level defaults and
error handling.  Used by the FastAPI router.
"""

from __future__ import annotations

import logging
from typing import Any

from src.infrastructure.adapters.secondary.external.volcengine.voice_chat_api import (
    VolcengineVoiceChatAPI,
)

logger = logging.getLogger(__name__)


class VolcengineRTCChatAdapter:
    """Manage RTC AI voice/video chat lifecycle."""

    def __init__(self, ak: str, sk: str, app_id: str) -> None:
        self._api = VolcengineVoiceChatAPI(ak, sk)
        self._app_id = app_id

    async def start_session(
        self,
        room_id: str,
        bot_user_id: str,
        model_endpoint_id: str,
        *,
        target_user_ids: list[str] | None = None,
        welcome_message: str = "你好，有什么可以帮你的吗？",
        system_messages: list[str] | None = None,
        voice_type: str = "BV001_streaming",
    ) -> dict[str, Any]:
        """Start a real-time AI voice chat session."""
        logger.info(
            "Starting RTC voice chat: room=%s endpoint=%s",
            room_id,
            model_endpoint_id,
        )
        return await self._api.start_voice_chat(
            app_id=self._app_id,
            room_id=room_id,
            bot_user_id=bot_user_id,
            model_endpoint_id=model_endpoint_id,
            target_user_ids=target_user_ids,
            welcome_message=welcome_message,
            system_messages=system_messages,
            voice_type=voice_type,
        )

    async def stop_session(
        self,
        room_id: str,
        bot_user_id: str,
    ) -> dict[str, Any]:
        """Stop a real-time AI voice chat session."""
        logger.info("Stopping RTC voice chat: room=%s", room_id)
        return await self._api.stop_voice_chat(
            app_id=self._app_id,
            room_id=room_id,
            bot_user_id=bot_user_id,
        )
