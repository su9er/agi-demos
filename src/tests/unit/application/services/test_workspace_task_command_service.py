"""Unit tests for WorkspaceTaskCommandService."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.application.services.workspace_task_command_service import WorkspaceTaskCommandService
from src.domain.events.types import AgentEventType
from src.domain.model.workspace.workspace_task import WorkspaceTask, WorkspaceTaskStatus


def _make_task(
    *,
    task_id: str = "wt-1",
    status: WorkspaceTaskStatus = WorkspaceTaskStatus.TODO,
    assignee_user_id: str | None = None,
    assignee_agent_id: str | None = None,
) -> WorkspaceTask:
    return WorkspaceTask(
        id=task_id,
        workspace_id="ws-1",
        title="Investigate integration issue",
        description="details",
        created_by="owner-1",
        assignee_user_id=assignee_user_id,
        assignee_agent_id=assignee_agent_id,
        status=status,
        metadata={"source": "test"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.unit
class TestWorkspaceTaskCommandService:
    @pytest.mark.asyncio
    async def test_create_task_queues_assigned_then_created_events(self) -> None:
        task_service = AsyncMock()
        task_service.create_task.return_value = _make_task(assignee_user_id="user-2")
        command_service = WorkspaceTaskCommandService(task_service)

        task = await command_service.create_task(
            workspace_id="ws-1",
            actor_user_id="user-1",
            title="Task",
            assignee_user_id="user-2",
        )

        events = command_service.consume_pending_events()

        assert task.assignee_user_id == "user-2"
        assert [event.event_type for event in events] == [
            AgentEventType.WORKSPACE_TASK_ASSIGNED,
            AgentEventType.WORKSPACE_TASK_CREATED,
        ]
        assert events[0].payload["task_id"] == task.id
        assert events[1].payload["task"]["id"] == task.id
        assert command_service.consume_pending_events() == []

    @pytest.mark.asyncio
    async def test_start_task_queues_status_changed_event(self) -> None:
        task_service = AsyncMock()
        task_service.start_task.return_value = _make_task(status=WorkspaceTaskStatus.IN_PROGRESS)
        command_service = WorkspaceTaskCommandService(task_service)

        task = await command_service.start_task(
            workspace_id="ws-1",
            task_id="wt-1",
            actor_user_id="user-1",
        )

        events = command_service.consume_pending_events()

        assert task.status == WorkspaceTaskStatus.IN_PROGRESS
        assert len(events) == 1
        assert events[0].event_type == AgentEventType.WORKSPACE_TASK_STATUS_CHANGED
        assert events[0].payload["new_status"] == WorkspaceTaskStatus.IN_PROGRESS.value



    @pytest.mark.asyncio
    async def test_update_task_queues_child_and_root_snapshot_events(self) -> None:
        task_service = AsyncMock()
        child_task = _make_task(task_id="child-1", status=WorkspaceTaskStatus.IN_PROGRESS)
        child_task.metadata = {"root_goal_task_id": "root-1", "source": "test"}
        root_task = _make_task(task_id="root-1", status=WorkspaceTaskStatus.IN_PROGRESS)
        root_task.metadata = {"task_role": "goal_root"}
        task_service.update_task.return_value = child_task
        task_service.get_task.return_value = root_task
        command_service = WorkspaceTaskCommandService(task_service)

        task = await command_service.update_task(
            workspace_id="ws-1",
            task_id="child-1",
            actor_user_id="user-1",
            metadata={"pending_leader_adjudication": True},
        )

        events = command_service.consume_pending_events()

        assert task is child_task
        assert [event.event_type for event in events] == [
            AgentEventType.WORKSPACE_TASK_UPDATED,
            AgentEventType.WORKSPACE_TASK_UPDATED,
        ]
        assert events[0].payload["task"]["id"] == "child-1"
        assert events[1].payload["task"]["id"] == "root-1"
        task_service.get_task.assert_awaited_once_with(
            workspace_id="ws-1",
            task_id="root-1",
            actor_user_id="user-1",
        )

    @pytest.mark.asyncio
    async def test_complete_task_queues_status_change_then_root_snapshot(self) -> None:
        task_service = AsyncMock()
        child_task = _make_task(task_id="child-2", status=WorkspaceTaskStatus.DONE)
        child_task.metadata = {"root_goal_task_id": "root-2", "source": "test"}
        root_task = _make_task(task_id="root-2", status=WorkspaceTaskStatus.IN_PROGRESS)
        root_task.metadata = {"task_role": "goal_root"}
        task_service.complete_task.return_value = child_task
        task_service.get_task.return_value = root_task
        command_service = WorkspaceTaskCommandService(task_service)

        task = await command_service.complete_task(
            workspace_id="ws-1",
            task_id="child-2",
            actor_user_id="user-1",
        )

        events = command_service.consume_pending_events()

        assert task is child_task
        assert [event.event_type for event in events] == [
            AgentEventType.WORKSPACE_TASK_STATUS_CHANGED,
            AgentEventType.WORKSPACE_TASK_UPDATED,
        ]
        assert events[0].payload["task"]["id"] == "child-2"
        assert events[0].payload["new_status"] == WorkspaceTaskStatus.DONE.value
        assert events[1].payload["task"]["id"] == "root-2"
