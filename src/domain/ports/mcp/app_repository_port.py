"""
MCPAppRepositoryPort - Abstract interface for MCP App persistence.

This port defines the contract for storing and querying MCP App entities,
following hexagonal architecture principles.
"""

from abc import abstractmethod
from typing import Any, Protocol, runtime_checkable

from src.domain.model.mcp.app import MCPApp


@runtime_checkable
class MCPAppRepositoryPort(Protocol):
    """Repository interface for persisting MCP App entities."""

    @abstractmethod
    async def save(self, app: MCPApp) -> MCPApp:
        """Save or update an MCP App.

        Args:
            app: The MCPApp entity to persist.

        Returns:
            The saved MCPApp entity.
        """
        ...

    @abstractmethod
    async def find_by_id(self, app_id: str) -> MCPApp | None:
        """Find an MCP App by its ID.

        Args:
            app_id: Unique identifier of the app.

        Returns:
            MCPApp if found, None otherwise.
        """
        ...

    @abstractmethod
    async def find_by_server_and_tool(self, server_id: str, tool_name: str) -> MCPApp | None:
        """Find an MCP App by its server and tool name combination.

        Args:
            server_id: The MCP server ID.
            tool_name: The tool name that declares this app.

        Returns:
            MCPApp if found, None otherwise.
        """
        ...

    @abstractmethod
    async def find_by_project_server_name_and_tool(
        self, project_id: str, server_name: str, tool_name: str
    ) -> MCPApp | None:
        """Find an MCP App by project, server name, and tool name.

        Uses the same key as the DB unique constraint
        (project_id, server_name, tool_name) for reliable deduplication.

        Args:
            project_id: Project ID for scoping.
            server_name: Human-readable server name.
            tool_name: The tool name that declares this app.

        Returns:
            MCPApp if found, None otherwise.
        """
        ...

    @abstractmethod
    async def find_by_project(
        self, project_id: str, include_disabled: bool = False
    ) -> list[MCPApp]:
        """Find all MCP Apps for a project.

        Args:
            project_id: Project ID for scoping.
            include_disabled: Whether to include disabled apps.

        Returns:
            List of MCPApp entities.
        """
        ...

    @abstractmethod
    async def find_ready_by_project(self, project_id: str) -> list[MCPApp]:
        """Find all ready-to-render MCP Apps for a project.

        Args:
            project_id: Project ID for scoping.

        Returns:
            List of MCPApp entities with status READY.
        """
        ...

    @abstractmethod
    async def find_by_tenant(
        self,
        tenant_id: str,
        *,
        include_disabled: bool = False,
    ) -> list[MCPApp]:
        """Find all MCP apps belonging to a tenant.

        Args:
            tenant_id: The tenant identifier.
            include_disabled: If True, include disabled apps.

        Returns:
            List of MCP apps for the tenant.
        """
        ...

    @abstractmethod
    async def delete(self, app_id: str) -> bool:
        """Delete an MCP App.

        Args:
            app_id: Unique identifier of the app.

        Returns:
            True if deleted, False if not found.
        """
        ...

    @abstractmethod
    async def delete_by_server(self, server_id: str) -> int:
        """Delete all MCP Apps for a server.

        Args:
            server_id: The MCP server ID.

        Returns:
            Number of apps deleted.
        """
        ...

    @abstractmethod
    async def disable_by_server(self, server_id: str) -> int:
        """Disable all MCP Apps for a server.

        Called when a server is disabled to mark its apps as unreachable.

        Args:
            server_id: The MCP server ID.

        Returns:
            Number of apps disabled.
        """
        ...

    @abstractmethod
    async def update_lifecycle_metadata(self, app_id: str, metadata: dict[str, Any]) -> bool:
        """Merge lifecycle metadata into existing app metadata.

        Args:
            app_id: Unique identifier of the app.
            metadata: Metadata dict to merge into existing lifecycle_metadata.

        Returns:
            True if updated, False if not found.
        """
        ...
