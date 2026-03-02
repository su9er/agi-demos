"""Backward compatibility - re-exports from config subpackage."""

from src.domain.model.agent.config.tenant_agent_config import (
    ConfigType,
    TenantAgentConfig,
)

__all__ = [
    "ConfigType",
    "TenantAgentConfig",
]
