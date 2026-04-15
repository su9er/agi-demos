"""Unit tests for audit query service hook-specific query helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.audit_query_service import AuditQueryService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_runtime_hook_entries_uses_runtime_hook_filters() -> None:
    repo = MagicMock()
    repo.find_by_tenant_filtered = AsyncMock(return_value=[])
    repo.count_by_tenant_filtered = AsyncMock(return_value=0)
    service = AuditQueryService(audit_repo=repo)

    await service.list_runtime_hook_entries(
        "tenant-1",
        hook_name="before_response",
        executor_kind="script",
        hook_family="mutating",
        isolation_mode="host",
        limit=25,
        offset=10,
    )

    repo.find_by_tenant_filtered.assert_awaited_once_with(
        "tenant-1",
        action=None,
        action_prefix="runtime_hook.",
        resource_type="runtime_hook",
        actor=None,
        detail_filters={
            "hook_name": "before_response",
            "executor_kind": "script",
            "hook_family": "mutating",
            "isolation_mode": "host",
        },
        start_time=None,
        end_time=None,
        limit=25,
        offset=10,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_summarize_runtime_hook_entries_uses_runtime_hook_filters() -> None:
    repo = MagicMock()
    repo.summarize_by_tenant_filtered = AsyncMock(return_value={"total": 1})
    service = AuditQueryService(audit_repo=repo)

    summary = await service.summarize_runtime_hook_entries(
        "tenant-1",
        action="runtime_hook.custom_execution_failed",
        executor_kind="script",
        isolation_mode="sandbox",
    )

    assert summary == {"total": 1}
    repo.summarize_by_tenant_filtered.assert_awaited_once_with(
        "tenant-1",
        action="runtime_hook.custom_execution_failed",
        action_prefix="runtime_hook.",
        resource_type="runtime_hook",
        detail_filters={
            "executor_kind": "script",
            "isolation_mode": "sandbox",
        },
    )
