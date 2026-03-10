"""Volcengine external adapter package.

Public API:
    generate_rtc_token  -- RTC join token generator
    VolcengineVoiceChatAPI  -- low-level RTC voice chat client
    VolcengineRTCChatAdapter  -- high-level session adapter
    VolcengineASRAdapter  -- ASR (speech-to-text) adapter
    VolcengineTTSAdapter  -- TTS (text-to-speech) adapter
"""

from __future__ import annotations

from src.infrastructure.adapters.secondary.external.volcengine.rtc_chat_adapter import (
    VolcengineRTCChatAdapter,
)
from src.infrastructure.adapters.secondary.external.volcengine.rtc_token import (
    generate_rtc_token,
)
from src.infrastructure.adapters.secondary.external.volcengine.voice_chat_api import (
    VolcengineVoiceChatAPI,
)

__all__ = [
    "VolcengineRTCChatAdapter",
    "VolcengineVoiceChatAPI",
    "generate_rtc_token",
]
