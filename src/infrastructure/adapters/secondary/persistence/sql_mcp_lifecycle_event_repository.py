"""SQLAlchemy implementation of MCPLifecycleEventRepositoryPort."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.adapters.secondary.persistence.models import MCPLifecycleEvent


class SqlMCPLifecycleEventRepository:
    """Persists MCP lifecycle audit events to PostgreSQL.

    Implements :class:`MCPLifecycleEventRepositoryPort`.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_event(
        self,
        *,
        tenant_id: str,
        project_id: str,
        event_type: str,
        status: str,
        server_id: str | None = None,
        app_id: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist a lifecycle audit event."""
        if not tenant_id or not project_id:
            return

        event = MCPLifecycleEvent(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            server_id=server_id,
            app_id=app_id,
            event_type=event_type,
            status=status,
            error_message=error_message,
            metadata_json=metadata or {},
        )
        self._db.add(event)
        await self._db.flush()
