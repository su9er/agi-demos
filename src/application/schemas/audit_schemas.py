from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuditEntryResponse(BaseModel):
    id: str
    timestamp: datetime
    actor: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    tenant_id: str | None = None
    details: dict[str, object] = Field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditEntryResponse]
    total: int
    limit: int
    offset: int


class RuntimeHookAuditSummaryResponse(BaseModel):
    total: int
    action_counts: dict[str, int] = Field(default_factory=dict)
    executor_counts: dict[str, int] = Field(default_factory=dict)
    family_counts: dict[str, int] = Field(default_factory=dict)
    isolation_mode_counts: dict[str, int] = Field(default_factory=dict)
    latest_timestamp: datetime | None = None
