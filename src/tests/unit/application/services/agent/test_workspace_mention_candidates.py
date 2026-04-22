"""Unit tests for WorkspaceMentionCandidatesResolver (Phase-5 G7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.application.services.agent.workspace_mention_candidates import (
    WorkspaceMentionCandidatesResolver,
)
from src.domain.model.agent.conversation.conversation import Conversation
from src.domain.model.agent.conversation.conversation_mode import ConversationMode


@dataclass
class _StubAgent:
    agent_id: str
    workspace_id: str = "ws-1"
    display_name: str | None = None
    label: str | None = None
    status: str = "idle"
    is_active: bool = True
    description: str | None = None
    config: dict = field(default_factory=dict)
    hex_q: int | None = None
    hex_r: int | None = None
    theme_color: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None


class _StubWorkspaceAgentRepo:
    def __init__(self, agents: list[_StubAgent]) -> None:
        self._agents = agents

    async def find_by_workspace(
        self,
        workspace_id: str,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ):
        result = [a for a in self._agents if a.workspace_id == workspace_id]
        if active_only:
            result = [a for a in result if a.is_active]
        return result

    async def save(self, workspace_agent):
        raise NotImplementedError

    async def find_by_id(self, workspace_agent_id: str):
        return None

    async def find_by_workspace_and_agent_id(self, workspace_id, agent_id):
        return None

    async def find_by_workspace_and_hex(self, workspace_id, hex_q, hex_r):
        return None

    async def delete(self, workspace_agent_id: str) -> bool:
        return False


def _make_conversation(
    *,
    workspace_id: str | None = None,
    participants: list[str] | None = None,
) -> Conversation:
    conv = Conversation(
        project_id="p-1",
        tenant_id="t-1",
        user_id="u-1",
        title="chat",
        conversation_mode=ConversationMode.MULTI_AGENT_SHARED,
    )
    if workspace_id is not None:
        conv.workspace_id = workspace_id
    if participants is not None:
        conv.participant_agents = list(participants)
    return conv


async def test_workspace_linked_returns_workspace_agents() -> None:
    repo = _StubWorkspaceAgentRepo(
        [
            _StubAgent(agent_id="alice", display_name="Alice", label="leader"),
            _StubAgent(agent_id="bob", display_name="Bob", status="thinking"),
            _StubAgent(agent_id="inactive", is_active=False),
        ]
    )
    resolver = WorkspaceMentionCandidatesResolver(repo)  # type: ignore[arg-type]
    conv = _make_conversation(workspace_id="ws-1", participants=["alice"])

    candidates = await resolver.resolve(conv)

    assert [c.agent_id for c in candidates] == ["alice", "bob"]
    assert all(c.source == "workspace" for c in candidates)
    assert candidates[0].display_name == "Alice"
    assert candidates[0].label == "leader"
    assert candidates[1].status == "thinking"


async def test_workspace_linked_include_inactive() -> None:
    repo = _StubWorkspaceAgentRepo(
        [
            _StubAgent(agent_id="alice"),
            _StubAgent(agent_id="inactive", is_active=False),
        ]
    )
    resolver = WorkspaceMentionCandidatesResolver(repo)  # type: ignore[arg-type]
    conv = _make_conversation(workspace_id="ws-1")

    candidates = await resolver.resolve(conv, include_inactive=True)

    assert [c.agent_id for c in candidates] == ["alice", "inactive"]
    assert candidates[1].is_active is False


async def test_no_workspace_falls_back_to_participants() -> None:
    repo = _StubWorkspaceAgentRepo([])
    resolver = WorkspaceMentionCandidatesResolver(repo)  # type: ignore[arg-type]
    conv = _make_conversation(participants=["charlie", "dana"])

    candidates = await resolver.resolve(conv)

    assert [c.agent_id for c in candidates] == ["charlie", "dana"]
    assert all(c.source == "conversation" for c in candidates)
    assert all(c.display_name is None for c in candidates)


async def test_no_workspace_empty_roster() -> None:
    repo = _StubWorkspaceAgentRepo([])
    resolver = WorkspaceMentionCandidatesResolver(repo)  # type: ignore[arg-type]
    conv = _make_conversation(participants=[])

    candidates = await resolver.resolve(conv)

    assert candidates == []
