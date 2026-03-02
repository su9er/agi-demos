"""Sandbox idle reaper initialization for startup."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.configuration.config import get_settings
from src.infrastructure.adapters.secondary.persistence.database import async_session_factory

if TYPE_CHECKING:
    from src.application.services.sandbox_idle_reaper import SandboxIdleReaper

logger = logging.getLogger(__name__)

# Module-level reference for shutdown
_sandbox_idle_reaper: SandboxIdleReaper | None = None


async def initialize_sandbox_idle_reaper() -> SandboxIdleReaper | None:
    """Initialize and start the sandbox idle reaper background task.

    Creates a SandboxIdleReaper that periodically checks for idle sandboxes
    and terminates them, optionally syncing workspace state beforehand.

    Returns:
        The started SandboxIdleReaper instance, or None if initialization fails.
    """
    global _sandbox_idle_reaper

    settings = get_settings()

    if settings.sandbox_idle_timeout_seconds <= 0:
        logger.info("Sandbox idle reaper disabled (sandbox_idle_timeout_seconds <= 0)")
        return None

    try:
        from src.application.services.sandbox_idle_reaper import SandboxIdleReaper
        from src.application.services.workspace_sync_service import WorkspaceSyncService
        from src.infrastructure.adapters.secondary.sandbox.mcp_sandbox_adapter import (
            MCPSandboxAdapter,
        )

        # Create sandbox adapter for termination operations
        sandbox_adapter = MCPSandboxAdapter()

        # Create workspace sync service for pre-destroy hooks
        workspace_sync = WorkspaceSyncService(
            workspace_base=settings.sandbox_workspace_base,
        )

        _sandbox_idle_reaper = SandboxIdleReaper(
            idle_timeout_seconds=settings.sandbox_idle_timeout_seconds,
            check_interval_seconds=settings.sandbox_idle_check_interval_seconds,
            session_factory=async_session_factory,
            sandbox_adapter=sandbox_adapter,
            workspace_sync=workspace_sync,
        )
        _sandbox_idle_reaper.start()
        logger.info(
            "Sandbox idle reaper started (timeout=%ds, interval=%ds)",
            settings.sandbox_idle_timeout_seconds,
            settings.sandbox_idle_check_interval_seconds,
        )
        return _sandbox_idle_reaper
    except Exception:
        logger.warning("Failed to start sandbox idle reaper", exc_info=True)
        return None


async def shutdown_sandbox_idle_reaper() -> None:
    """Stop the sandbox idle reaper background task."""
    global _sandbox_idle_reaper

    if _sandbox_idle_reaper:
        try:
            await _sandbox_idle_reaper.stop()
            logger.info("Sandbox idle reaper stopped")
        except Exception:
            logger.warning("Error stopping sandbox idle reaper", exc_info=True)
        finally:
            _sandbox_idle_reaper = None
