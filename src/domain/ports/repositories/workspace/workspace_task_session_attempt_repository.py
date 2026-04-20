from abc import ABC, abstractmethod

from src.domain.model.workspace.workspace_task_session_attempt import (
    WorkspaceTaskSessionAttempt,
    WorkspaceTaskSessionAttemptStatus,
)


class WorkspaceTaskSessionAttemptRepository(ABC):
    """Repository interface for workspace task session attempts."""

    @abstractmethod
    async def save(self, attempt: WorkspaceTaskSessionAttempt) -> WorkspaceTaskSessionAttempt:
        """Save a workspace task session attempt."""

    @abstractmethod
    async def find_by_id(self, attempt_id: str) -> WorkspaceTaskSessionAttempt | None:
        """Find attempt by ID."""

    @abstractmethod
    async def find_by_workspace_task_id(
        self,
        workspace_task_id: str,
        *,
        statuses: list[WorkspaceTaskSessionAttemptStatus] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkspaceTaskSessionAttempt]:
        """List attempts for a workspace task."""

    @abstractmethod
    async def find_active_by_workspace_task_id(
        self, workspace_task_id: str
    ) -> WorkspaceTaskSessionAttempt | None:
        """Find the active attempt for a workspace task, if any."""

    @abstractmethod
    async def find_by_conversation_id(
        self, conversation_id: str
    ) -> WorkspaceTaskSessionAttempt | None:
        """Find the attempt bound to a scoped conversation."""
