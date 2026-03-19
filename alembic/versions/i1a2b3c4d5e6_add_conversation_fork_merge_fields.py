"""Add fork_source_id, fork_context_snapshot, merge_strategy to conversations table.

Revision ID: i1a2b3c4d5e6
Revises: h1a2b3c4d5e6
Create Date: 2026-03-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i1a2b3c4d5e6"
down_revision: Union[str, None] = "h1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "fork_source_id",
            sa.String(),
            sa.ForeignKey("conversations.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("fork_context_snapshot", sa.Text(), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "merge_strategy",
            sa.String(20),
            nullable=False,
            server_default="result_only",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "merge_strategy")
    op.drop_column("conversations", "fork_context_snapshot")
    op.drop_column("conversations", "fork_source_id")
