from __future__ import annotations

import logging
from datetime import datetime

from src.domain.model.audit.audit_entry import AuditEntry
from src.domain.ports.repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)


class AuditQueryService:
    def __init__(self, audit_repo: AuditRepository) -> None:
        self._repo = audit_repo

    async def list_entries(
        self,
        tenant_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditEntry], int]:
        items = await self._repo.find_by_tenant(tenant_id, limit=limit, offset=offset)
        total = await self._repo.count_by_tenant(tenant_id)
        return items, total

    async def list_entries_filtered(
        self,
        tenant_id: str,
        *,
        action: str | None = None,
        action_prefix: str | None = None,
        resource_type: str | None = None,
        actor: str | None = None,
        detail_filters: dict[str, str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditEntry], int]:
        items = await self._repo.find_by_tenant_filtered(
            tenant_id,
            action=action,
            action_prefix=action_prefix,
            resource_type=resource_type,
            actor=actor,
            detail_filters=detail_filters,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )
        total = await self._repo.count_by_tenant_filtered(
            tenant_id,
            action=action,
            action_prefix=action_prefix,
            resource_type=resource_type,
            actor=actor,
            detail_filters=detail_filters,
            start_time=start_time,
            end_time=end_time,
        )
        return items, total

    async def list_runtime_hook_entries(
        self,
        tenant_id: str,
        *,
        action: str | None = None,
        hook_name: str | None = None,
        executor_kind: str | None = None,
        hook_family: str | None = None,
        isolation_mode: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditEntry], int]:
        detail_filters = {
            key: value
            for key, value in {
                "hook_name": hook_name,
                "executor_kind": executor_kind,
                "hook_family": hook_family,
                "isolation_mode": isolation_mode,
            }.items()
            if value is not None
        }
        return await self.list_entries_filtered(
            tenant_id,
            action=action,
            action_prefix="runtime_hook.",
            resource_type="runtime_hook",
            detail_filters=detail_filters,
            limit=limit,
            offset=offset,
        )

    async def summarize_runtime_hook_entries(
        self,
        tenant_id: str,
        *,
        action: str | None = None,
        hook_name: str | None = None,
        executor_kind: str | None = None,
        hook_family: str | None = None,
        isolation_mode: str | None = None,
    ) -> dict[str, object]:
        detail_filters = {
            key: value
            for key, value in {
                "hook_name": hook_name,
                "executor_kind": executor_kind,
                "hook_family": hook_family,
                "isolation_mode": isolation_mode,
            }.items()
            if value is not None
        }
        return await self._repo.summarize_by_tenant_filtered(
            tenant_id,
            action=action,
            action_prefix="runtime_hook.",
            resource_type="runtime_hook",
            detail_filters=detail_filters,
        )
