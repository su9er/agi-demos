"""Startup wiring for :class:`WorkspaceAttemptRecoveryService`.

Always-on. Runs a sweep at boot to recover orphaned attempts left over from
a prior process and then starts the periodic watchdog loop that rescues
attempts stale from this process.

Disable only for tests / emergencies via
``WORKSPACE_ATTEMPT_RECOVERY_ENABLED=false``.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from src.infrastructure.adapters.secondary.persistence.database import async_session_factory

if TYPE_CHECKING:
    from src.infrastructure.agent.workspace.workspace_attempt_recovery import (
        WorkspaceAttemptRecoveryService,
    )

logger = logging.getLogger(__name__)

_ENABLED_ENV = "WORKSPACE_ATTEMPT_RECOVERY_ENABLED"
_STALE_ENV = "WORKSPACE_ATTEMPT_RECOVERY_STALE_SECONDS"
_INTERVAL_ENV = "WORKSPACE_ATTEMPT_RECOVERY_INTERVAL_SECONDS"
_GRACE_ENV = "WORKSPACE_ATTEMPT_RECOVERY_STARTUP_GRACE_SECONDS"

_recovery: WorkspaceAttemptRecoveryService | None = None


def _enabled() -> bool:
    raw = os.environ.get(_ENABLED_ENV)
    if raw is None:
        return True  # always-on by default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return value if value > 0 else default


async def initialize_attempt_recovery() -> WorkspaceAttemptRecoveryService | None:
    global _recovery

    if not _enabled():
        logger.info(
            "workspace_attempt_recovery.disabled",
            extra={"event": "workspace_attempt_recovery.disabled"},
        )
        return None

    try:
        from src.infrastructure.adapters.primary.web.routers.workspace_leader_bootstrap import (
            schedule_autonomy_tick,
        )
        from src.infrastructure.agent.workspace.workspace_attempt_recovery import (
            DEFAULT_CHECK_INTERVAL_SECONDS,
            DEFAULT_STALE_SECONDS,
            DEFAULT_STARTUP_GRACE_SECONDS,
            WorkspaceAttemptRecoveryService,
        )
        from src.infrastructure.agent.workspace.workspace_goal_runtime import (
            apply_workspace_worker_report,
        )
        from src.infrastructure.agent.workspace.workspace_supervisor import (
            get_workspace_supervisor,
        )

        def _liveness_lookup() -> list[str]:
            supervisor = get_workspace_supervisor()
            if supervisor is None:
                return []
            return list(supervisor.get_liveness_snapshot().keys())

        _recovery = WorkspaceAttemptRecoveryService(
            session_factory=async_session_factory,
            apply_report=apply_workspace_worker_report,
            schedule_tick=schedule_autonomy_tick,
            liveness_lookup=_liveness_lookup,
            stale_seconds=_int_env(_STALE_ENV, DEFAULT_STALE_SECONDS),
            startup_grace_seconds=_int_env(
                _GRACE_ENV, DEFAULT_STARTUP_GRACE_SECONDS
            ),
            check_interval_seconds=_int_env(
                _INTERVAL_ENV, DEFAULT_CHECK_INTERVAL_SECONDS
            ),
        )
        await _recovery.start()
        return _recovery
    except Exception:
        logger.warning(
            "workspace_attempt_recovery.start_failed",
            exc_info=True,
            extra={"event": "workspace_attempt_recovery.start_failed"},
        )
        return None


async def shutdown_attempt_recovery() -> None:
    global _recovery
    if _recovery is None:
        return
    try:
        await _recovery.stop()
    except Exception:
        logger.warning(
            "workspace_attempt_recovery.stop_failed",
            exc_info=True,
            extra={"event": "workspace_attempt_recovery.stop_failed"},
        )
    finally:
        _recovery = None
