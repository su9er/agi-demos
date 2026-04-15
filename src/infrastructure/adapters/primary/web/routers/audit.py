from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.schemas.audit_schemas import (
    AuditEntryResponse,
    AuditLogListResponse,
    RuntimeHookAuditSummaryResponse,
)
from src.application.services.audit_query_service import AuditQueryService
from src.domain.model.auth.user import User
from src.infrastructure.adapters.primary.web.dependencies import (
    get_current_user,
)
from src.infrastructure.adapters.primary.web.routers.agent.access import require_tenant_access
from src.infrastructure.adapters.secondary.persistence.database import get_db
from src.infrastructure.adapters.secondary.persistence.sql_audit_repository import (
    SqlAuditRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/audit-logs",
    tags=["audit-logs"],
)


def _build_service(db: AsyncSession) -> AuditQueryService:
    return AuditQueryService(audit_repo=SqlAuditRepository(db))


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    await require_tenant_access(db, current_user, tenant_id)
    service = _build_service(db)
    items, total = await service.list_entries(tenant_id, limit=limit, offset=offset)
    return AuditLogListResponse(
        items=[
            AuditEntryResponse(
                id=e.id,
                timestamp=e.timestamp,
                actor=e.actor,
                action=e.action,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                tenant_id=e.tenant_id,
                details=e.details,
                ip_address=e.ip_address,
                user_agent=e.user_agent,
            )
            for e in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/filter", response_model=AuditLogListResponse)
async def list_audit_logs_filtered(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    await require_tenant_access(db, current_user, tenant_id)
    service = _build_service(db)
    items, total = await service.list_entries_filtered(
        tenant_id,
        action=action,
        resource_type=resource_type,
        actor=actor,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(
        items=[
            AuditEntryResponse(
                id=e.id,
                timestamp=e.timestamp,
                actor=e.actor,
                action=e.action,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                tenant_id=e.tenant_id,
                details=e.details,
                ip_address=e.ip_address,
                user_agent=e.user_agent,
            )
            for e in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runtime-hooks", response_model=AuditLogListResponse)
async def list_runtime_hook_audit_logs(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    action: str | None = Query(default=None),
    hook_name: str | None = Query(default=None),
    executor_kind: str | None = Query(default=None),
    hook_family: str | None = Query(default=None),
    isolation_mode: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    """List runtime hook audit entries with hook-specific filters."""
    await require_tenant_access(db, current_user, tenant_id)
    service = _build_service(db)
    items, total = await service.list_runtime_hook_entries(
        tenant_id,
        action=action,
        hook_name=hook_name,
        executor_kind=executor_kind,
        hook_family=hook_family,
        isolation_mode=isolation_mode,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(
        items=[
            AuditEntryResponse(
                id=e.id,
                timestamp=e.timestamp,
                actor=e.actor,
                action=e.action,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                tenant_id=e.tenant_id,
                details=e.details,
                ip_address=e.ip_address,
                user_agent=e.user_agent,
            )
            for e in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runtime-hooks/summary", response_model=RuntimeHookAuditSummaryResponse)
async def get_runtime_hook_audit_summary(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    action: str | None = Query(default=None),
    hook_name: str | None = Query(default=None),
    executor_kind: str | None = Query(default=None),
    hook_family: str | None = Query(default=None),
    isolation_mode: str | None = Query(default=None),
) -> RuntimeHookAuditSummaryResponse:
    """Return aggregate runtime hook audit information for observability."""
    await require_tenant_access(db, current_user, tenant_id)
    service = _build_service(db)
    summary = await service.summarize_runtime_hook_entries(
        tenant_id,
        action=action,
        hook_name=hook_name,
        executor_kind=executor_kind,
        hook_family=hook_family,
        isolation_mode=isolation_mode,
    )
    return RuntimeHookAuditSummaryResponse(**cast(dict[str, Any], summary))
