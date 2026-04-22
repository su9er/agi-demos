"""Phase-5 G5 — workspace.default_blocking_categories column.

Adds a JSON column holding the list of HITL blocking categories that
apply by default to every conversation linked to this workspace. The
column is additive with ``server_default='[]'`` so existing rows
backfill automatically.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g5f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "g2d1e2f3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "default_blocking_categories_json",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "default_blocking_categories_json")
