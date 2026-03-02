"""Backward compatibility - re-exports from config subpackage."""

from src.domain.model.agent.config.tenant_skill_config import (
    TenantSkillAction,
    TenantSkillConfig,
)

__all__ = [
    "TenantSkillAction",
    "TenantSkillConfig",
]
