"""Volcengine RTC endpoints for voice/video call integration.

Endpoints:
    POST /api/v1/volcengine/token          -- Generate RTC join token
    POST /api/v1/volcengine/voice-chat/start  -- Start AI voice chat
    POST /api/v1/volcengine/voice-chat/stop   -- Stop AI voice chat
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.configuration.config import Settings, get_settings
from src.infrastructure.adapters.secondary.external.volcengine.rtc_chat_adapter import (
    VolcengineRTCChatAdapter,
)
from src.infrastructure.adapters.secondary.external.volcengine.rtc_token import (
    generate_rtc_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/volcengine", tags=["Volcengine RTC"])


# ── Request / Response Models ────────────────────────────────────────


class TokenRequest(BaseModel):
    room_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)
    expire_time: int = Field(default=3600, ge=60, le=86400)


class TokenResponse(BaseModel):
    token: str
    app_id: str


class VoiceChatStartRequest(BaseModel):
    room_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)
    model_endpoint_id: str | None = None
    welcome_message: str = "你好，有什么可以帮你的吗？"
    voice_type: str = "BV001_streaming"
    system_messages: list[str] | None = None


class VoiceChatStopRequest(BaseModel):
    room_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)


# ── Dependencies ─────────────────────────────────────────────────────


def _require_rtc_config(
    settings: Settings = Depends(get_settings),
) -> Settings:
    """Validate that all required Volcengine RTC env vars are present."""
    if not settings.volc_rtc_app_id or not settings.volc_rtc_app_key:
        raise HTTPException(
            status_code=500,
            detail="Volcengine RTC not configured (RTC_APP_ID / RTC_APP_KEY)",
        )
    return settings


def _require_voice_chat_config(
    settings: Settings = Depends(get_settings),
) -> Settings:
    """Validate RTC + AK/SK + endpoint are configured."""
    if not settings.volc_ak or not settings.volc_sk:
        raise HTTPException(
            status_code=500,
            detail="Volcengine credentials missing (VOLC_AK / VOLC_SK)",
        )
    if not settings.volc_rtc_app_id:
        raise HTTPException(
            status_code=500,
            detail="Volcengine RTC_APP_ID not configured",
        )
    return settings


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/token", response_model=TokenResponse)
async def get_rtc_token(
    req: TokenRequest,
    settings: Settings = Depends(_require_rtc_config),
) -> TokenResponse:
    """Generate an RTC join token for the given room and user."""
    token = generate_rtc_token(
        app_id=settings.volc_rtc_app_id,  # type: ignore[arg-type]
        app_key=settings.volc_rtc_app_key,  # type: ignore[arg-type]
        room_id=req.room_id,
        user_id=req.user_id,
        expire_time=req.expire_time,
    )
    return TokenResponse(
        token=token,
        app_id=settings.volc_rtc_app_id,  # type: ignore[arg-type]
    )


@router.post("/voice-chat/start")
async def start_voice_chat(
    req: VoiceChatStartRequest,
    settings: Settings = Depends(_require_voice_chat_config),
) -> dict[str, Any]:
    """Start an AI voice chat session in the given room."""
    endpoint_id = req.model_endpoint_id or settings.volc_doubao_endpoint_id
    if not endpoint_id:
        raise HTTPException(
            status_code=400,
            detail=("model_endpoint_id required (or set DOUBAO_ENDPOINT_ID env var)"),
        )

    adapter = VolcengineRTCChatAdapter(
        ak=settings.volc_ak,  # type: ignore[arg-type]
        sk=settings.volc_sk,  # type: ignore[arg-type]
        app_id=settings.volc_rtc_app_id,  # type: ignore[arg-type]
    )
    return await adapter.start_session(
        room_id=req.room_id,
        bot_user_id=req.user_id,
        model_endpoint_id=endpoint_id,
        target_user_ids=[req.user_id],
        welcome_message=req.welcome_message,
        system_messages=req.system_messages,
        voice_type=req.voice_type,
    )


@router.post("/voice-chat/stop")
async def stop_voice_chat(
    req: VoiceChatStopRequest,
    settings: Settings = Depends(_require_voice_chat_config),
) -> dict[str, Any]:
    """Stop an AI voice chat session."""
    adapter = VolcengineRTCChatAdapter(
        ak=settings.volc_ak,  # type: ignore[arg-type]
        sk=settings.volc_sk,  # type: ignore[arg-type]
        app_id=settings.volc_rtc_app_id,  # type: ignore[arg-type]
    )
    return await adapter.stop_session(
        room_id=req.room_id,
        bot_user_id=req.user_id,
    )
