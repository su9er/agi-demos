"""Focused unit tests for scope-sensitive env-var repository writes."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.model.agent.tool_environment_variable import (
    EnvVarScope,
    ToolEnvironmentVariable,
)
from src.infrastructure.adapters.secondary.persistence.sql_tool_environment_variable_repository import (
    SqlToolEnvironmentVariableRepository,
)


def _make_env_var(
    *,
    env_var_id: str,
    tenant_id: str,
    tool_name: str,
    variable_name: str,
    project_id: str | None = None,
    encrypted_value: str = "encrypted_value",
) -> ToolEnvironmentVariable:
    return ToolEnvironmentVariable(
        id=env_var_id,
        tenant_id=tenant_id,
        project_id=project_id,
        tool_name=tool_name,
        variable_name=variable_name,
        encrypted_value=encrypted_value,
        scope=EnvVarScope.PROJECT if project_id else EnvVarScope.TENANT,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upsert_project_scope_uses_exact_scope_lookup(monkeypatch) -> None:
    """Project-scoped writes must not consult the tenant-fallback read path."""
    session = AsyncMock(spec=AsyncSession)
    repo = SqlToolEnvironmentVariableRepository(session)
    tenant_env_var = _make_env_var(
        env_var_id="env-tenant-1",
        tenant_id="tenant-1",
        tool_name="search",
        variable_name="API_KEY",
    )
    project_env_var = _make_env_var(
        env_var_id="env-project-1",
        tenant_id="tenant-1",
        tool_name="search",
        variable_name="API_KEY",
        project_id="project-1",
        encrypted_value="project_encrypted_value",
    )

    exact_get_mock = AsyncMock(return_value=None)
    create_mock = AsyncMock(return_value=project_env_var)
    fallback_get_mock = AsyncMock(return_value=tenant_env_var)

    monkeypatch.setattr(repo, "_get_exact_scope", exact_get_mock)
    monkeypatch.setattr(repo, "create", create_mock)
    monkeypatch.setattr(repo, "get", fallback_get_mock)

    result = await repo.upsert(project_env_var)

    exact_get_mock.assert_awaited_once_with(
        tenant_id="tenant-1",
        tool_name="search",
        variable_name="API_KEY",
        project_id="project-1",
    )
    fallback_get_mock.assert_not_awaited()
    create_mock.assert_awaited_once_with(project_env_var)
    assert result is project_env_var
