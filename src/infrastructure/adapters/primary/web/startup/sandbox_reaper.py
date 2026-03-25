"""Sandbox idle reaper initialization for startup."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.configuration.config import get_settings
from src.configuration.di_container import DIContainer
from src.infrastructure.adapters.secondary.persistence.database import async_session_factory

if TYPE_CHECKING:
    from src.application.services.sandbox_idle_reaper import SandboxIdleReaper

logger = logging.getLogger(__name__)

# Module-level reference for shutdown
_sandbox_idle_reaper: SandboxIdleReaper | None = None


async def initialize_sandbox_idle_reaper(container: DIContainer) -> SandboxIdleReaper | None:
    """Initialize and start the sandbox idle reaper background task.

    Creates a SandboxIdleReaper that periodically checks for idle sandboxes
    and terminates them, optionally syncing workspace state beforehand.

    Returns:
        The started SandboxIdleReaper instance, or None if initialization fails.
    """
    global _sandbox_idle_reaper

    settings = get_settings()

    if not settings.sandbox_idle_reaper_enabled:
        logger.info("Sandbox idle reaper disabled (sandbox_idle_reaper_enabled=false)")
        return None

    if settings.sandbox_idle_timeout_seconds <= 0:
        logger.info("Sandbox idle reaper disabled (sandbox_idle_timeout_seconds <= 0)")
        return None

    try:
        from src.application.services.sandbox_idle_reaper import SandboxIdleReaper
        from src.application.services.workspace_sync_service import WorkspaceSyncService
        from src.infrastructure.adapters.secondary.persistence.sql_project_sandbox_repository import (
            SqlProjectSandboxRepository,
        )
        # Reuse application singleton adapter to avoid split in-memory state
        sandbox_adapter = container.sandbox_adapter()

        async def _persist_access_activity(sandbox_id: str, accessed_at: datetime) -> None:
            async with async_session_factory() as db:
                repo = SqlProjectSandboxRepository(db)
                association = await repo.find_by_sandbox(sandbox_id)
                if association is None:
                    return
                if accessed_at.tzinfo is None:
                    association.last_accessed_at = accessed_at.replace(tzinfo=UTC)
                else:
                    association.last_accessed_at = accessed_at.astimezone(UTC)
                await repo.save(association)

        sandbox_adapter.set_access_persist_callback(_persist_access_activity)

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
            is_recently_active=sandbox_adapter.is_recently_active,
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
