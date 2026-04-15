"""Integration-style tests for runtime hook audit queryability."""

from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.audit_query_service import AuditQueryService
from src.infrastructure.adapters.secondary.persistence.sql_audit_repository import (
    SqlAuditRepository,
)
from src.infrastructure.agent.plugins.custom_hook_executor import execute_custom_hook
from src.infrastructure.audit.audit_log_service import AuditLogService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_hook_audit_events_are_queryable_via_service(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _session_factory():
        yield db_session

    monkeypatch.setattr(
        "src.infrastructure.audit.audit_log_service.async_session_factory",
        _session_factory,
    )
    monkeypatch.setattr(
        "src.infrastructure.agent.plugins.custom_hook_executor.get_audit_service",
        lambda: AuditLogService(backend="database"),
    )

    await execute_custom_hook(
        executor_kind="script",
        source_ref="src/infrastructure/agent/hooks/scripts/demo_runtime_hook.py",
        entrypoint="append_demo_response_instruction",
        hook_family="mutating",
        payload={
            "tenant_id": "tenant-1",
            "response_instructions": [],
            "hook_settings": {"isolation_mode": "host"},
            "hook_identity": {"hook_name": "before_response", "plugin_name": "__custom__"},
        },
    )

    service = AuditQueryService(audit_repo=SqlAuditRepository(db_session))
    items, total = await service.list_runtime_hook_entries(
        "tenant-1",
        hook_name="before_response",
        executor_kind="script",
        isolation_mode="host",
    )
    summary = await service.summarize_runtime_hook_entries(
        "tenant-1",
        hook_name="before_response",
        executor_kind="script",
        isolation_mode="host",
    )

    assert total == 2
    assert len(items) == 2
    assert summary["total"] == 2
    assert summary["action_counts"]["runtime_hook.custom_execution_started"] == 1
    assert summary["action_counts"]["runtime_hook.custom_execution_succeeded"] == 1
    assert summary["executor_counts"]["script"] == 2
    assert summary["isolation_mode_counts"]["host"] == 2
