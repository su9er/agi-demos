"""Security and permission policy helpers for runtime hook execution."""

from __future__ import annotations

from typing import Any

from src.domain.model.agent.tenant_agent_config import HookExecutorKind

DEFAULT_CUSTOM_HOOK_TIMEOUT_SECONDS = 5.0
MAX_CUSTOM_HOOK_TIMEOUT_SECONDS = 10.0
MIN_CUSTOM_HOOK_TIMEOUT_SECONDS = 0.1
TIMEOUT_SETTING_KEY = "timeout_seconds"
ISOLATION_MODE_SETTING_KEY = "isolation_mode"
HOST_ISOLATION_MODE = "host"
SANDBOX_ISOLATION_MODE = "sandbox"
ALLOWED_ISOLATION_MODES: frozenset[str] = frozenset(
    {HOST_ISOLATION_MODE, SANDBOX_ISOLATION_MODE}
)

ALLOWED_HOOK_FAMILIES_BY_EXECUTOR: dict[str, frozenset[str]] = {
    HookExecutorKind.BUILTIN.value: frozenset(
        {"observational", "mutating", "policy", "side_effect"}
    ),
    HookExecutorKind.SCRIPT.value: frozenset(
        {"observational", "mutating", "side_effect"}
    ),
    HookExecutorKind.PLUGIN.value: frozenset(
        {"observational", "mutating", "policy", "side_effect"}
    ),
}


def normalize_hook_family(value: str | None) -> str:
    """Normalize hook family spellings into the canonical runtime form."""
    normalized = (value or "").strip().lower().replace("-", "_")
    return normalized


def normalize_executor_kind(value: str | None) -> str:
    """Normalize executor kind strings."""
    return (value or "").strip().lower()


def is_executor_allowed_for_family(
    *,
    executor_kind: str,
    hook_family: str,
) -> bool:
    """Return whether an executor kind may run the given hook family."""
    allowed = ALLOWED_HOOK_FAMILIES_BY_EXECUTOR.get(normalize_executor_kind(executor_kind))
    if allowed is None:
        return False
    return normalize_hook_family(hook_family) in allowed


def resolve_custom_hook_timeout(settings: dict[str, Any]) -> float:
    """Resolve and validate the timeout for a custom runtime hook."""
    raw_timeout = settings.get(TIMEOUT_SETTING_KEY, DEFAULT_CUSTOM_HOOK_TIMEOUT_SECONDS)
    if not isinstance(raw_timeout, (int, float)):
        raise ValueError(f"{TIMEOUT_SETTING_KEY} must be numeric")
    timeout_seconds = float(raw_timeout)
    if not (MIN_CUSTOM_HOOK_TIMEOUT_SECONDS <= timeout_seconds <= MAX_CUSTOM_HOOK_TIMEOUT_SECONDS):
        raise ValueError(
            f"{TIMEOUT_SETTING_KEY} must be between "
            f"{MIN_CUSTOM_HOOK_TIMEOUT_SECONDS} and {MAX_CUSTOM_HOOK_TIMEOUT_SECONDS} seconds"
        )
    return timeout_seconds


def resolve_custom_hook_isolation_mode(settings: dict[str, Any]) -> str:
    """Resolve and validate the execution isolation mode for a custom hook."""
    raw_mode = settings.get(ISOLATION_MODE_SETTING_KEY, HOST_ISOLATION_MODE)
    if not isinstance(raw_mode, str):
        raise ValueError(f"{ISOLATION_MODE_SETTING_KEY} must be a string")
    normalized_mode = raw_mode.strip().lower()
    if normalized_mode not in ALLOWED_ISOLATION_MODES:
        raise ValueError(
            f"{ISOLATION_MODE_SETTING_KEY} must be one of: "
            f"{', '.join(sorted(ALLOWED_ISOLATION_MODES))}"
        )
    return normalized_mode
