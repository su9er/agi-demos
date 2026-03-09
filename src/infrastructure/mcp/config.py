"""
MCP Configuration.

This module previously contained Pydantic configuration models (McpLocalConfig,
McpRemoteConfig, McpWebSocketConfig, McpOAuthConfig, McpConfig, MCPStatusType,
MCPStatus) which have been migrated to domain models:

- src.domain.model.mcp.transport.TransportConfig (replaces McpLocalConfig, McpRemoteConfig, McpWebSocketConfig)
- src.domain.model.mcp.transport.TransportType (replaces type field)
- src.domain.model.mcp.connection.ConnectionState (replaces MCPStatusType)
- src.domain.model.mcp.connection.ConnectionInfo (replaces MCPStatus)

New code should import from the domain layer directly.
"""
