"""Unit tests for WorkspaceRosterValidator (G4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import override

import pytest

from src.application.services.agent.workspace_roster_validator import (
    WorkspaceRosterValidator,
)
from src.domain.model.agent.conversation.conversation import Conversation
from src.domain.model.agent.conversation.conversation_mode import ConversationMode
from src.domain.model.agent.conversation.errors import ParticipantNotPresentError
from src.domain.model.workspace.workspace_agent import WorkspaceAgent
from src.domain.ports.repositories.workspace.workspace_agent_repository import (
    WorkspaceAgentRepository,
)


def _binding(agent_id: str, workspace_id: str = "ws-1") -> WorkspaceAgent:
    return WorkspaceAgent(
        workspace_id=workspace_id,
        agent_id=agent_id,
        is_active=True,
    )


@dataclass
class _StubAgentRepo(WorkspaceAgentRepository):
    bindings: list[WorkspaceAgent] = field(default_factory=list)

    @override
    async def save(self, workspace_agent: WorkspaceAgent) -> WorkspaceAgent:  # pragma: no cover
        self.bindings.append(workspace_agent)
        return workspace_agent

    @override
    async def find_by_id(
        self, workspace_agent_id: str
    ) -> WorkspaceAgent | None:  # pragma: no cover
        return next((b for b in self.bindings if b.id == workspace_agent_id), None)

    @override
    async def find_by_workspace(
        self,
        workspace_id: str,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkspaceAgent]:
        results = [b for b in self.bindings if b.workspace_id == workspace_id]
        if active_only:
            results = [b for b in results if b.is_active]
        return results[offset : offset + limit]

    @override
    async def find_by_workspace_and_agent_id(
        self, workspace_id: str, agent_id: str
    ) -> WorkspaceAgent | None:  # pragma: no cover
        return next(
            (
                b
                for b in self.bindings
                if b.workspace_id == workspace_id and b.agent_id == agent_id
            ),
            None,
        )

    @override
    async def find_by_workspace_and_hex(
        self, workspace_id: str, hex_q: int, hex_r: int
    ) -> list[WorkspaceAgent]:  # pragma: no cover
        return []

    @override
    async def delete(self, workspace_agent_id: str) -> bool:  # pragma: no cover
        return False


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
    }
    defaults.update(overrides)
    return Conversation(**defaults)  # type: ignore[arg-type]


class TestWorkspaceRosterValidator:
    async def test_subset_passes(self) -> None:
        repo = _StubAgentRepo(bindings=[_binding("agent-a"), _binding("agent-b")])
        validator = WorkspaceRosterValidator(workspace_agent_repository=repo)
        await validator.assert_valid(_conv(participant_agents=["agent-a"]))

    async def test_equal_set_passes(self) -> None:
        repo = _StubAgentRepo(bindings=[_binding("agent-a"), _binding("agent-b")])
        validator = WorkspaceRosterValidator(workspace_agent_repository=repo)
        await validator.assert_valid(
            _conv(participant_agents=["agent-a", "agent-b"])
        )

    async def test_missing_participant_raises(self) -> None:
        repo = _StubAgentRepo(bindings=[_binding("agent-a")])
        validator = WorkspaceRosterValidator(workspace_agent_repository=repo)
        with pytest.raises(ParticipantNotPresentError) as exc_info:
            await validator.assert_valid(
                _conv(participant_agents=["agent-a", "ghost"])
            )
        assert "ghost" in str(exc_info.value)
        assert "ws-1" in str(exc_info.value)

    async def test_inactive_binding_is_ignored(self) -> None:
        bindings = [_binding("agent-a")]
        bindings[0].is_active = False
        repo = _StubAgentRepo(bindings=bindings)
        validator = WorkspaceRosterValidator(workspace_agent_repository=repo)
        with pytest.raises(ParticipantNotPresentError):
            await validator.assert_valid(_conv(participant_agents=["agent-a"]))

    async def test_no_workspace_id_is_noop(self) -> None:
        repo = _StubAgentRepo()
        validator = WorkspaceRosterValidator(workspace_agent_repository=repo)
        # coordinator required for AUTONOMOUS, but workspace-less conversations
        # skip the invariant entirely — so construct a non-autonomous.
        await validator.assert_valid(
            _conv(
                conversation_mode=ConversationMode.MULTI_AGENT_SHARED,
                coordinator_agent_id=None,
                workspace_id=None,
                participant_agents=["agent-z"],
            )
        )

    async def test_empty_participant_list_is_noop(self) -> None:
        repo = _StubAgentRepo()
        validator = WorkspaceRosterValidator(workspace_agent_repository=repo)
        await validator.assert_valid(
            _conv(
                conversation_mode=ConversationMode.MULTI_AGENT_SHARED,
                coordinator_agent_id=None,
                participant_agents=[],
            )
        )
