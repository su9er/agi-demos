"""MCPLifecycleEventRepositoryPort - Abstract interface for MCP lifecycle event persistence.

This port defines the contract for recording lifecycle audit events
for MCP server and app operations, following hexagonal architecture principles.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MCPLifecycleEventRepositoryPort(Protocol):
    """Repository interface for persisting MCP lifecycle audit events."""

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
        """Persist a lifecycle audit event.

        Args:
            tenant_id: Tenant that owns the resource.
            project_id: Project scope.
            event_type: Type of lifecycle event (e.g. 'server.created').
            status: Event status (e.g. 'success', 'failure').
            server_id: Optional MCP server ID.
            app_id: Optional MCP app ID.
            error_message: Optional error description.
            metadata: Optional event metadata dict.
        """
        ...
