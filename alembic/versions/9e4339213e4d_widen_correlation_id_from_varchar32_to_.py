"""widen correlation_id from varchar32 to varchar100

Revision ID: 9e4339213e4d
Revises: f9c1d2e3a4b5
Create Date: 2026-03-06 09:18:51.172862

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e4339213e4d"
down_revision: str | Sequence[str] | None = "f9c1d2e3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen correlation_id to accommodate prefixed UUIDs (e.g. 'cron:<uuid>')."""
    op.alter_column(
        "agent_execution_events",
        "correlation_id",
        existing_type=sa.VARCHAR(length=32),
        type_=sa.String(length=100),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert correlation_id back to VARCHAR(32)."""
    op.alter_column(
        "agent_execution_events",
        "correlation_id",
        existing_type=sa.String(length=100),
        type_=sa.VARCHAR(length=32),
        existing_nullable=True,
    )
