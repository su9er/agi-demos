"""add workspace task session attempts

Revision ID: m5e6f7a8b9c0
Revises: l4d5e6f7a8b9
Create Date: 2026-04-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "l4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_task_session_attempts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_task_id", sa.String(), nullable=False),
        sa.Column("root_goal_task_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("conversation_id", sa.String(), nullable=True),
        sa.Column("worker_agent_id", sa.String(), nullable=True),
        sa.Column("leader_agent_id", sa.String(), nullable=True),
        sa.Column("candidate_summary", sa.Text(), nullable=True),
        sa.Column(
            "candidate_artifacts_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column(
            "candidate_verifications_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("leader_feedback", sa.Text(), nullable=True),
        sa.Column("adjudication_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["leader_agent_id"], ["agent_definitions.id"]),
        sa.ForeignKeyConstraint(
            ["root_goal_task_id"], ["workspace_tasks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["worker_agent_id"], ["agent_definitions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["workspace_task_id"], ["workspace_tasks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_task_id",
            "attempt_number",
            name="uq_workspace_task_session_attempts_task_attempt",
        ),
    )
    op.create_index(
        "ix_workspace_task_session_attempts_task_status",
        "workspace_task_session_attempts",
        ["workspace_task_id", "status"],
    )
    op.create_index(
        "ix_workspace_task_session_attempts_root_created",
        "workspace_task_session_attempts",
        ["root_goal_task_id", "created_at"],
    )
    op.create_index(
        "ix_workspace_task_session_attempts_conversation_id",
        "workspace_task_session_attempts",
        ["conversation_id"],
    )
    op.create_index(
        "ix_workspace_task_session_attempts_workspace_id",
        "workspace_task_session_attempts",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_task_session_attempts_workspace_id",
        table_name="workspace_task_session_attempts",
    )
    op.drop_index(
        "ix_workspace_task_session_attempts_conversation_id",
        table_name="workspace_task_session_attempts",
    )
    op.drop_index(
        "ix_workspace_task_session_attempts_root_created",
        table_name="workspace_task_session_attempts",
    )
    op.drop_index(
        "ix_workspace_task_session_attempts_task_status",
        table_name="workspace_task_session_attempts",
    )
    op.drop_table("workspace_task_session_attempts")
