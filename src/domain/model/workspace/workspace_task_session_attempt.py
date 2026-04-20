from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from src.domain.shared_kernel import Entity


class WorkspaceTaskSessionAttemptStatus(str, Enum):
    """Lifecycle states for a single workspace-task execution attempt."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_LEADER_ADJUDICATION = "awaiting_leader_adjudication"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass(kw_only=True)
class WorkspaceTaskSessionAttempt(Entity):
    """A discrete execution attempt for a single workspace task."""

    workspace_task_id: str
    root_goal_task_id: str
    workspace_id: str
    attempt_number: int
    status: WorkspaceTaskSessionAttemptStatus = WorkspaceTaskSessionAttemptStatus.PENDING
    conversation_id: str | None = None
    worker_agent_id: str | None = None
    leader_agent_id: str | None = None
    candidate_summary: str | None = None
    candidate_artifacts: list[str] = field(default_factory=list)
    candidate_verifications: list[str] = field(default_factory=list)
    leader_feedback: str | None = None
    adjudication_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.workspace_task_id:
            raise ValueError("workspace_task_id cannot be empty")
        if not self.root_goal_task_id:
            raise ValueError("root_goal_task_id cannot be empty")
        if not self.workspace_id:
            raise ValueError("workspace_id cannot be empty")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be >= 1")
