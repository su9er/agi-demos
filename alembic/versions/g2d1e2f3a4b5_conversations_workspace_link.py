"""g2 conversations: add workspace_id + linked_workspace_task_id FKs.

Revision ID: g2d1e2f3a4b5
Revises: g1a0b1c2d3e4
Create Date: 2026-05-11

Track G2 (Phase-5 Workspace-first pivot). ``GoalContract`` was removed
in G1; autonomous conversations now reference a ``Workspace`` for goal
state, and optionally a specific ``WorkspaceTask`` for narrow targeting.

Both columns are nullable FKs so legacy rows remain valid. The
autonomous-mode invariant that requires ``workspace_id`` to be set is
enforced at the domain layer (``Conversation.assert_autonomous_invariants``),
not by a check constraint, because non-autonomous rows are legitimately
unlinked.

``ON DELETE SET NULL`` is used rather than CASCADE: losing a workspace
or task should orphan the conversation pointer, not delete the message
history.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g2d1e2f3a4b5"
down_revision: str | Sequence[str] | None = "g1a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add conversations.workspace_id + linked_workspace_task_id."""
    bind = op.get_bind()
    bind.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
    op.add_column(
        "conversations",
        sa.Column("workspace_id", sa.String(), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("linked_workspace_task_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_workspace_id",
        "conversations",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_conversations_linked_workspace_task_id",
        "conversations",
        "workspace_tasks",
        ["linked_workspace_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_conversations_workspace_id",
        "conversations",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the workspace link columns."""
    bind = op.get_bind()
    bind.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
    op.drop_index("ix_conversations_workspace_id", table_name="conversations")
    op.drop_constraint(
        "fk_conversations_linked_workspace_task_id", "conversations", type_="foreignkey"
    )
    op.drop_constraint("fk_conversations_workspace_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "linked_workspace_task_id")
    op.drop_column("conversations", "workspace_id")
