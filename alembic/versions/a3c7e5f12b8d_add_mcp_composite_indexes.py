"""Add composite indexes for MCP servers and apps.

Revision ID: a3c7e5f12b8d
Revises: 8b2f6a9d1c4e
Create Date: 2026-03-09

Adds indexes to speed up common query patterns:
- mcp_servers: (project_id, enabled) and (tenant_id, enabled)
- mcp_apps: (tenant_id, status)
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a3c7e5f12b8d"
down_revision = "8b2f6a9d1c4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_mcp_servers_project_enabled", "mcp_servers", ["project_id", "enabled"])
    op.create_index("ix_mcp_servers_tenant_enabled", "mcp_servers", ["tenant_id", "enabled"])
    op.create_index("ix_mcp_apps_tenant_status", "mcp_apps", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_mcp_apps_tenant_status", table_name="mcp_apps")
    op.drop_index("ix_mcp_servers_tenant_enabled", table_name="mcp_servers")
    op.drop_index("ix_mcp_servers_project_enabled", table_name="mcp_servers")
