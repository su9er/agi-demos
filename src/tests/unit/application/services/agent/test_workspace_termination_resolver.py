"""Unit tests for WorkspaceTerminationResolver (Phase-5 · G3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import override

from src.application.services.agent.workspace_termination_resolver import (
    WorkspaceTerminationResolver,
    build_context_from_task,
)
from src.domain.model.agent.conversation.conversation import Conversation
from src.domain.model.agent.conversation.conversation_mode import ConversationMode
from src.domain.model.agent.conversation.termination import BudgetCounters
from src.domain.model.workspace.workspace_task import WorkspaceTask, WorkspaceTaskStatus
from src.domain.ports.repositories.workspace.workspace_task_repository import (
    WorkspaceTaskRepository,
)


def _conv(**overrides: object) -> Conversation:
    defaults: dict[str, object] = {
        "id": "conv-1",
        "title": "Test",
        "user_id": "user-1",
        "project_id": "proj-1",
        "tenant_id": "tenant-1",
        "conversation_mode": ConversationMode.AUTONOMOUS,
        "coordinator_agent_id": "agent-a",
        "participant_agents": ["agent-a"],
        "workspace_id": "ws-1",
        "linked_workspace_task_id": "task-1",
    }
    defaults.update(overrides)
    return Conversation(**defaults)  # type: ignore[arg-type]


def _task(
    *,
    task_id: str = "task-1",
    status: WorkspaceTaskStatus = WorkspaceTaskStatus.IN_PROGRESS,
    title: str = "Deliver beta",
    assignee_agent_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> WorkspaceTask:
    task = WorkspaceTask(
        workspace_id="ws-1",
        title=title,
        created_by="user-1",
        status=status,
        assignee_agent_id=assignee_agent_id,
        metadata=dict(metadata or {}),
    )
    task.id = task_id  # Entity base assigns uuid by default; pin for tests.
    return task


@dataclass
class _StubTaskRepo(WorkspaceTaskRepository):
    by_id: dict[str, WorkspaceTask] = field(default_factory=dict)

    @override
    async def save(self, task: WorkspaceTask) -> WorkspaceTask:  # pragma: no cover
        self.by_id[task.id] = task
        return task

    @override
    async def find_by_id(self, task_id: str) -> WorkspaceTask | None:
        return self.by_id.get(task_id)

    @override
    async def find_by_workspace(
        self, workspace_id: str, *, include_archived: bool = False
    ) -> list[WorkspaceTask]:  # pragma: no cover
        return [t for t in self.by_id.values() if t.workspace_id == workspace_id]

    @override
    async def find_root_by_objective_id(
        self, objective_id: str
    ) -> WorkspaceTask | None:  # pragma: no cover
        return None

    @override
    async def find_by_root_goal_task_id(
        self, root_goal_task_id: str
    ) -> list[WorkspaceTask]:  # pragma: no cover
        return []

    @override
    async def delete(self, task_id: str) -> bool:  # pragma: no cover
        return self.by_id.pop(task_id, None) is not None


class TestBuildContextFromTask:
    def test_done_task_populates_goal_signal(self) -> None:
        task = _task(status=WorkspaceTaskStatus.DONE, assignee_agent_id="agent-a")
        ctx = build_context_from_task(
            conversation_id="c1",
            user_id="u1",
            task=task,
        )
        assert ctx.goal_completed_event_id == f"workspace_task:{task.id}:done"
        assert ctx.goal_completed_summary == "Deliver beta"
        assert ctx.goal_completed_actor == "agent-a"

    def test_non_done_task_leaves_goal_signal_empty(self) -> None:
        task = _task(status=WorkspaceTaskStatus.IN_PROGRESS)
        ctx = build_context_from_task(conversation_id="c1", user_id="u1", task=task)
        assert ctx.goal_completed_event_id == ""
        assert ctx.goal_completed_summary == ""

    def test_missing_task_leaves_everything_empty(self) -> None:
        ctx = build_context_from_task(conversation_id="c1", user_id="u1", task=None)
        assert ctx.goal_completed_event_id == ""
        assert ctx.max_turns is None
        assert ctx.max_usd is None
        assert ctx.max_wall_seconds is None

    def test_budgets_lifted_from_metadata(self) -> None:
        task = _task(metadata={"max_turns": 10, "max_usd": 2.5, "max_wall_seconds": 600})
        ctx = build_context_from_task(conversation_id="c1", user_id="u1", task=task)
        assert ctx.max_turns == 10
        assert ctx.max_usd == 2.5
        assert ctx.max_wall_seconds == 600

    def test_negative_or_invalid_budgets_drop_to_none(self) -> None:
        task = _task(metadata={"max_turns": 0, "max_usd": "garbage", "max_wall_seconds": -5})
        ctx = build_context_from_task(conversation_id="c1", user_id="u1", task=task)
        assert ctx.max_turns is None
        assert ctx.max_usd is None
        assert ctx.max_wall_seconds is None

    def test_title_truncated_at_500_chars(self) -> None:
        task = _task(status=WorkspaceTaskStatus.DONE, title="x" * 1000)
        ctx = build_context_from_task(conversation_id="c1", user_id="u1", task=task)
        assert len(ctx.goal_completed_summary) == 500

    def test_counters_passthrough(self) -> None:
        task = _task()
        counters = BudgetCounters(turns=5, usd=0.25, wall_seconds=42)
        ctx = build_context_from_task(
            conversation_id="c1",
            user_id="u1",
            task=task,
            counters=counters,
        )
        assert ctx.counters is counters


class TestResolver:
    async def test_resolve_linked_task(self) -> None:
        task = _task(status=WorkspaceTaskStatus.DONE)
        repo = _StubTaskRepo(by_id={task.id: task})
        resolver = WorkspaceTerminationResolver(task_repository=repo)

        ctx = await resolver.resolve(_conv())
        assert ctx.goal_completed_event_id == f"workspace_task:{task.id}:done"

    async def test_resolve_no_link_returns_empty_context(self) -> None:
        repo = _StubTaskRepo()
        resolver = WorkspaceTerminationResolver(task_repository=repo)

        ctx = await resolver.resolve(_conv(linked_workspace_task_id=None))
        assert ctx.goal_completed_event_id == ""
        assert ctx.max_turns is None

    async def test_resolve_dangling_link_returns_empty_context(self) -> None:
        repo = _StubTaskRepo()
        resolver = WorkspaceTerminationResolver(task_repository=repo)

        ctx = await resolver.resolve(_conv(linked_workspace_task_id="ghost"))
        assert ctx.goal_completed_event_id == ""
        assert ctx.max_turns is None
