"""Unit tests for sandbox reaper startup gating."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.adapters.primary.web.startup.sandbox_reaper import (
    initialize_sandbox_idle_reaper,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_initialize_sandbox_idle_reaper_disabled_by_flag() -> None:
    """Reaper should not start when SANDBOX_IDLE_REAPER_ENABLED is false."""
    container = MagicMock()
    container.sandbox_adapter = MagicMock(return_value=MagicMock())

    settings = MagicMock()
    settings.sandbox_idle_reaper_enabled = False
    settings.sandbox_idle_timeout_seconds = 1800
    settings.sandbox_idle_check_interval_seconds = 60
    settings.sandbox_workspace_base = "/tmp/workspace"

    with patch(
        "src.infrastructure.adapters.primary.web.startup.sandbox_reaper.get_settings",
        return_value=settings,
    ):
        reaper = await initialize_sandbox_idle_reaper(container)

    assert reaper is None
    container.sandbox_adapter.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_initialize_sandbox_idle_reaper_starts_when_enabled() -> None:
    """Reaper should start when enable flag is true and timeout is positive."""
    container = MagicMock()
    sandbox_adapter = MagicMock()
    sandbox_adapter.set_access_persist_callback = MagicMock()
    sandbox_adapter.is_recently_active = AsyncMock(return_value=True)
    container.sandbox_adapter = MagicMock(return_value=sandbox_adapter)

    settings = MagicMock()
    settings.sandbox_idle_reaper_enabled = True
    settings.sandbox_idle_timeout_seconds = 1800
    settings.sandbox_idle_check_interval_seconds = 60
    settings.sandbox_workspace_base = "/tmp/workspace"

    reaper_instance = MagicMock()
    reaper_instance.start = MagicMock()

    with (
        patch(
            "src.infrastructure.adapters.primary.web.startup.sandbox_reaper.get_settings",
            return_value=settings,
        ),
        patch(
            "src.application.services.sandbox_idle_reaper.SandboxIdleReaper",
            return_value=reaper_instance,
        ),
    ):
        reaper = await initialize_sandbox_idle_reaper(container)

    assert reaper is reaper_instance
    container.sandbox_adapter.assert_called_once_with()
    sandbox_adapter.set_access_persist_callback.assert_called_once()
    reaper_instance.start.assert_called_once_with()
