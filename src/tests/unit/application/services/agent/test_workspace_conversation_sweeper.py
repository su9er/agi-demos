"""Tests for WorkspaceConversationSweeper (Phase-5 G6)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from src.application.services.agent.workspace_conversation_sweeper import (
    WorkspaceConversationSweeper,
)
from src.application.services.agent.workspace_termination_resolver import (
    WorkspaceTerminationResolver,
)
from src.domain.model.agent import ConversationStatus
from src.domain.model.agent.conversation.conversation import Conversation
from src.domain.model.agent.conversation.conversation_mode import ConversationMode
from src.domain.model.workspace.workspace_task import (
    WorkspaceTask,
    WorkspaceTaskStatus,
)


def _make_conversation(
    *,
    conv_id: str,
    workspace_id: str | None = "ws-1",
    task_id: str | None = "task-1",
    mode: ConversationMode | None = ConversationMode.AUTONOMOUS,
    coordinator: str | None = "coord-agent",
    participants: list[str] | None = None,
) -> Conversation:
    return Conversation(
        id=conv_id,
        project_id="proj-1",
        tenant_id="tenant-1",
        user_id="user-1",
        title=f"Conv {conv_id}",
        conversation_mode=mode,
        coordinator_agent_id=coordinator,
        participant_agents=participants or [],
        workspace_id=workspace_id,
        linked_workspace_task_id=task_id,
    )


def _make_task(
    *,
    task_id: str = "task-1",
    status: WorkspaceTaskStatus = WorkspaceTaskStatus.IN_PROGRESS,
    title: str = "Ship G6",
    assignee: str | None = None,
) -> WorkspaceTask:
    task = WorkspaceTask(
        workspace_id="ws-1",
        title=title,
        created_by="user-1",
        status=status,
        assignee_agent_id=assignee,
    )
    task.id = task_id
    return task


class _StubConversationRepo:
    def __init__(self, conversations: list[Conversation]) -> None:
        self.by_id: dict[str, Conversation] = {c.id: c for c in conversations}
        self.saved: list[Conversation] = []

    async def list_by_workspace(
        self,
        workspace_id: str,
        *,
        mode: ConversationMode | None = None,
        status: ConversationStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Conversation]:
        out: list[Conversation] = []
        for c in self.by_id.values():
            if c.workspace_id != workspace_id:
                continue
            if mode is not None and c.conversation_mode is not mode:
                continue
            if status is not None and c.status is not status:
                continue
            out.append(c)
        return out[offset : offset + limit]

    async def save(self, conversation: Conversation) -> Conversation:
        self.by_id[conversation.id] = conversation
        self.saved.append(conversation)
        return conversation


class _StubTaskRepo:
    def __init__(self, tasks: dict[str, WorkspaceTask]) -> None:
        self.tasks = tasks

    async def find_by_id(self, task_id: str) -> WorkspaceTask | None:
        return self.tasks.get(task_id)

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - trampoline
        raise AttributeError(name)


@pytest.mark.unit
class TestWorkspaceConversationSweeper:
    async def test_archives_conversation_when_task_done(self) -> None:
        conv = _make_conversation(conv_id="c1")
        task = _make_task(task_id="task-1", status=WorkspaceTaskStatus.DONE, title="Win")

        conv_repo = _StubConversationRepo([conv])
        resolver = WorkspaceTerminationResolver(task_repository=_StubTaskRepo({"task-1": task}))  # type: ignore[arg-type]
        sweeper = WorkspaceConversationSweeper(
            conversation_repository=conv_repo,  # type: ignore[arg-type]
            termination_resolver=resolver,
        )

        result = await sweeper.sweep("ws-1")

        assert result.scanned == 1
        assert result.archived == 1
        assert result.archived_conversation_ids == ("c1",)
        assert conv.status is ConversationStatus.ARCHIVED
        assert conv.metadata["termination"]["reason"] == "goal_completed"
        assert conv.metadata["termination"]["triggered_by"] == "workspace_task:task-1:done"
        assert conv.metadata["termination"]["summary"] == "Win"
        assert isinstance(conv_repo.saved[0].updated_at, datetime)

    async def test_skips_conversation_when_task_in_progress(self) -> None:
        conv = _make_conversation(conv_id="c1")
        task = _make_task(status=WorkspaceTaskStatus.IN_PROGRESS)

        conv_repo = _StubConversationRepo([conv])
        resolver = WorkspaceTerminationResolver(task_repository=_StubTaskRepo({"task-1": task}))  # type: ignore[arg-type]
        sweeper = WorkspaceConversationSweeper(
            conversation_repository=conv_repo,  # type: ignore[arg-type]
            termination_resolver=resolver,
        )

        result = await sweeper.sweep("ws-1")

        assert result.scanned == 1
        assert result.archived == 0
        assert conv.status is ConversationStatus.ACTIVE
        assert conv_repo.saved == []

    async def test_skips_conversation_without_linked_task(self) -> None:
        conv = _make_conversation(conv_id="c1", task_id=None)

        conv_repo = _StubConversationRepo([conv])
        resolver = WorkspaceTerminationResolver(task_repository=_StubTaskRepo({}))  # type: ignore[arg-type]
        sweeper = WorkspaceConversationSweeper(
            conversation_repository=conv_repo,  # type: ignore[arg-type]
            termination_resolver=resolver,
        )

        result = await sweeper.sweep("ws-1")

        assert result.archived == 0
        assert conv.status is ConversationStatus.ACTIVE

    async def test_empty_workspace_returns_zero_counts(self) -> None:
        conv_repo = _StubConversationRepo([])
        resolver = WorkspaceTerminationResolver(task_repository=_StubTaskRepo({}))  # type: ignore[arg-type]
        sweeper = WorkspaceConversationSweeper(
            conversation_repository=conv_repo,  # type: ignore[arg-type]
            termination_resolver=resolver,
        )

        result = await sweeper.sweep("ws-1")

        assert result.scanned == 0
        assert result.archived == 0
        assert result.archived_conversation_ids == ()

    async def test_archives_multiple_done_conversations(self) -> None:
        convs = [
            _make_conversation(conv_id="c1", task_id="task-a"),
            _make_conversation(conv_id="c2", task_id="task-b"),
            _make_conversation(conv_id="c3", task_id="task-c"),
        ]
        tasks = {
            "task-a": _make_task(task_id="task-a", status=WorkspaceTaskStatus.DONE),
            "task-b": _make_task(task_id="task-b", status=WorkspaceTaskStatus.IN_PROGRESS),
            "task-c": _make_task(
                task_id="task-c",
                status=WorkspaceTaskStatus.DONE,
                assignee="agent-x",
            ),
        }

        conv_repo = _StubConversationRepo(convs)
        resolver = WorkspaceTerminationResolver(task_repository=_StubTaskRepo(tasks))  # type: ignore[arg-type]
        sweeper = WorkspaceConversationSweeper(
            conversation_repository=conv_repo,  # type: ignore[arg-type]
            termination_resolver=resolver,
        )

        result = await sweeper.sweep("ws-1")

        assert result.scanned == 3
        assert result.archived == 2
        assert set(result.archived_conversation_ids) == {"c1", "c3"}
        archived_actor = convs[2].metadata["termination"]["actor"]
        assert archived_actor == "agent-x"
