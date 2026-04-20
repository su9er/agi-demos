"""Unit tests for WorkspaceTaskSessionAttemptService."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.model.workspace.workspace_task_session_attempt import (
    WorkspaceTaskSessionAttempt,
    WorkspaceTaskSessionAttemptStatus,
)


def _make_attempt(
    *,
    attempt_id: str = "attempt-1",
    workspace_task_id: str = "task-1",
    attempt_number: int = 1,
    status: WorkspaceTaskSessionAttemptStatus = WorkspaceTaskSessionAttemptStatus.PENDING,
) -> WorkspaceTaskSessionAttempt:
    return WorkspaceTaskSessionAttempt(
        id=attempt_id,
        workspace_task_id=workspace_task_id,
        root_goal_task_id="root-1",
        workspace_id="ws-1",
        attempt_number=attempt_number,
        status=status,
        conversation_id=None,
        worker_agent_id="worker-1",
        leader_agent_id="leader-1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def attempt_repo() -> MagicMock:
    repo = MagicMock()
    repo.find_active_by_workspace_task_id = AsyncMock(return_value=None)
    repo.find_by_workspace_task_id = AsyncMock(return_value=[])
    repo.find_by_id = AsyncMock(return_value=None)
    repo.save = AsyncMock(side_effect=lambda attempt: attempt)
    return repo


@pytest.fixture
def attempt_service(attempt_repo: MagicMock):
    from src.application.services.workspace_task_session_attempt_service import (
        WorkspaceTaskSessionAttemptService,
    )

    return WorkspaceTaskSessionAttemptService(attempt_repo=attempt_repo)


@pytest.mark.unit
class TestWorkspaceTaskSessionAttemptService:
    @pytest.mark.asyncio
    async def test_create_attempt_starts_with_attempt_number_one(
        self,
        attempt_service,
        attempt_repo: MagicMock,
    ) -> None:
        attempt = await attempt_service.create_attempt(
            workspace_task_id="task-1",
            root_goal_task_id="root-1",
            workspace_id="ws-1",
            worker_agent_id="worker-1",
            leader_agent_id="leader-1",
        )

        assert attempt.attempt_number == 1
        assert attempt.status == WorkspaceTaskSessionAttemptStatus.PENDING
        attempt_repo.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_attempt_increments_attempt_number_after_retry(
        self,
        attempt_service,
        attempt_repo: MagicMock,
    ) -> None:
        attempt_repo.find_by_workspace_task_id.return_value = [_make_attempt(attempt_number=2)]

        attempt = await attempt_service.create_attempt(
            workspace_task_id="task-1",
            root_goal_task_id="root-1",
            workspace_id="ws-1",
            worker_agent_id="worker-1",
            leader_agent_id="leader-1",
        )

        assert attempt.attempt_number == 3

    @pytest.mark.asyncio
    async def test_create_attempt_rejects_when_active_attempt_exists(
        self,
        attempt_service,
        attempt_repo: MagicMock,
    ) -> None:
        attempt_repo.find_active_by_workspace_task_id.return_value = _make_attempt()

        with pytest.raises(ValueError, match="active session attempt"):
            await attempt_service.create_attempt(
                workspace_task_id="task-1",
                root_goal_task_id="root-1",
                workspace_id="ws-1",
                worker_agent_id="worker-1",
                leader_agent_id="leader-1",
            )

    @pytest.mark.asyncio
    async def test_record_candidate_output_moves_attempt_to_pending_adjudication(
        self,
        attempt_service,
        attempt_repo: MagicMock,
    ) -> None:
        attempt_repo.find_by_id.return_value = _make_attempt(
            status=WorkspaceTaskSessionAttemptStatus.RUNNING
        )

        updated = await attempt_service.record_candidate_output(
            "attempt-1",
            summary="Draft complete",
            artifacts=["artifact:1"],
            verifications=["check:1"],
            conversation_id="conv-123",
        )

        assert updated.status == WorkspaceTaskSessionAttemptStatus.AWAITING_LEADER_ADJUDICATION
        assert updated.candidate_summary == "Draft complete"
        assert updated.candidate_artifacts == ["artifact:1"]
        assert updated.candidate_verifications == ["check:1"]
        assert updated.conversation_id == "conv-123"

    @pytest.mark.asyncio
    async def test_accept_marks_attempt_accepted(
        self,
        attempt_service,
        attempt_repo: MagicMock,
    ) -> None:
        attempt_repo.find_by_id.return_value = _make_attempt(
            status=WorkspaceTaskSessionAttemptStatus.AWAITING_LEADER_ADJUDICATION
        )

        updated = await attempt_service.accept("attempt-1", leader_feedback="Looks good")

        assert updated.status == WorkspaceTaskSessionAttemptStatus.ACCEPTED
        assert updated.leader_feedback == "Looks good"
        assert updated.completed_at is not None
