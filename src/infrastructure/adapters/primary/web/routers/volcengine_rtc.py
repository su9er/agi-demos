"""Volcengine RTC endpoints for voice/video call integration.

Endpoints:
    POST /api/v1/volcengine/token          -- Generate RTC join token
    POST /api/v1/volcengine/voice-chat/start  -- Start AI voice chat
    POST /api/v1/volcengine/voice-chat/stop   -- Stop AI voice chat
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.configuration.config import Settings, get_settings
from src.infrastructure.adapters.secondary.external.volcengine.rtc_chat_adapter import (
    VolcengineRTCChatAdapter,
)
from src.infrastructure.adapters.secondary.external.volcengine.rtc_token import (
    generate_rtc_token,
)
from src.infrastructure.adapters.secondary.persistence.database import get_db
from src.infrastructure.persistence.llm_providers_models import (
    LLMProvider as LLMProviderORM,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/volcengine", tags=["Volcengine RTC"])


# -- Request / Response Models ------------------------------------------------


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
    welcome_message: str = (
        "\u4f60\u597d\uff0c\u6709\u4ec0\u4e48\u53ef\u4ee5\u5e2e\u4f60\u7684\u5417\uff1f"
    )
    voice_type: str = "BV001_streaming"
    system_messages: list[str] | None = None


class VoiceChatStopRequest(BaseModel):
    room_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)


# -- Resolved RTC Config -------------------------------------------------------


@dataclass(frozen=True)
class RTCConfig:
    """Resolved RTC configuration (DB-first, env-var fallback)."""

    rtc_app_id: str | None
    rtc_app_key: str | None
    volc_ak: str | None
    volc_sk: str | None
    doubao_endpoint_id: str | None


# -- Dependencies ---------------------------------------------------------------


async def _resolve_rtc_config(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> RTCConfig:
    """Resolve RTC config: prefer provider DB config, fall back to env vars."""
    db_config: dict[str, Any] = {}
    try:
        result = await db.execute(
            select(LLMProviderORM)
            .where(LLMProviderORM.provider_type.like("volcengine%"))
            .where(LLMProviderORM.is_active.is_(True))
            .limit(1)
        )
        provider = result.scalar_one_or_none()
        if provider and provider.config:
            db_config = provider.config
    except Exception:
        logger.warning("Failed to query volcengine provider config from DB", exc_info=True)

    return RTCConfig(
        rtc_app_id=db_config.get("rtc_app_id") or settings.volc_rtc_app_id,
        rtc_app_key=db_config.get("rtc_app_key") or settings.volc_rtc_app_key,
        volc_ak=db_config.get("volc_ak") or settings.volc_ak,
        volc_sk=db_config.get("volc_sk") or settings.volc_sk,
        doubao_endpoint_id=(
            db_config.get("doubao_endpoint_id") or settings.volc_doubao_endpoint_id
        ),
    )


def _require_rtc_fields(cfg: RTCConfig) -> None:
    """Raise 500 if core RTC fields (app_id / app_key) are missing."""
    if not cfg.rtc_app_id or not cfg.rtc_app_key:
        raise HTTPException(
            status_code=500,
            detail="Volcengine RTC not configured (RTC_APP_ID / RTC_APP_KEY)",
        )


def _require_voice_chat_fields(cfg: RTCConfig) -> None:
    """Raise 500 if voice-chat fields (AK/SK/app_id) are missing."""
    if not cfg.volc_ak or not cfg.volc_sk:
        raise HTTPException(
            status_code=500,
            detail="Volcengine credentials missing (VOLC_AK / VOLC_SK)",
        )
    if not cfg.rtc_app_id:
        raise HTTPException(
            status_code=500,
            detail="Volcengine RTC_APP_ID not configured",
        )


# -- Endpoints ------------------------------------------------------------------


@router.post("/token", response_model=TokenResponse)
async def get_rtc_token(
    req: TokenRequest,
    cfg: RTCConfig = Depends(_resolve_rtc_config),
) -> TokenResponse:
    """Generate an RTC join token for the given room and user."""
    _require_rtc_fields(cfg)
    token = generate_rtc_token(
        app_id=cfg.rtc_app_id,  # type: ignore[arg-type]
        app_key=cfg.rtc_app_key,  # type: ignore[arg-type]
        room_id=req.room_id,
        user_id=req.user_id,
        expire_time=req.expire_time,
    )
    return TokenResponse(
        token=token,
        app_id=cfg.rtc_app_id,  # type: ignore[arg-type]
    )


@router.post("/voice-chat/start")
async def start_voice_chat(
    req: VoiceChatStartRequest,
    cfg: RTCConfig = Depends(_resolve_rtc_config),
) -> dict[str, Any]:
    """Start an AI voice chat session in the given room."""
    _require_voice_chat_fields(cfg)
    endpoint_id = req.model_endpoint_id or cfg.doubao_endpoint_id
    if not endpoint_id:
        raise HTTPException(
            status_code=400,
            detail="model_endpoint_id required (or set DOUBAO_ENDPOINT_ID env var)",
        )

    adapter = VolcengineRTCChatAdapter(
        ak=cfg.volc_ak,  # type: ignore[arg-type]
        sk=cfg.volc_sk,  # type: ignore[arg-type]
        app_id=cfg.rtc_app_id,  # type: ignore[arg-type]
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
    cfg: RTCConfig = Depends(_resolve_rtc_config),
) -> dict[str, Any]:
    """Stop an AI voice chat session."""
    _require_voice_chat_fields(cfg)
    adapter = VolcengineRTCChatAdapter(
        ak=cfg.volc_ak,  # type: ignore[arg-type]
        sk=cfg.volc_sk,  # type: ignore[arg-type]
        app_id=cfg.rtc_app_id,  # type: ignore[arg-type]
    )
    return await adapter.stop_session(
        room_id=req.room_id,
        bot_user_id=req.user_id,
    )
