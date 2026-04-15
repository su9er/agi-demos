"""Backward compatibility - re-exports from config subpackage."""

from src.domain.model.agent.config.tenant_agent_config import (
    ConfigType,
    HookExecutorKind,
    RuntimeHookConfig,
    TenantAgentConfig,
)

__all__ = [
    "ConfigType",
    "HookExecutorKind",
    "RuntimeHookConfig",
    "TenantAgentConfig",
]
