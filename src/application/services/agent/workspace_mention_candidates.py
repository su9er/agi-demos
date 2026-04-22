"""Unified mention-candidate resolver for a conversation (Phase-5 G7).

When a conversation is linked to a workspace, the canonical source of
truth for "who can be @mentioned" is the **workspace agent roster**
(:class:`WorkspaceAgent`), not the conversation's own
``participant_agents`` snapshot.  This module exposes a small, pure
helper that mirrors the decision tree:

* ``workspace_id`` set → return active workspace agents, enriched with
  display_name / label / status / is_active.
* ``workspace_id`` unset → fall back to ``participant_agents`` on the
  conversation itself (legacy, still valid for project-scoped multi-
  agent conversations).

The resolver is **Agent-First by construction**: candidates are looked
up by set-membership (workspace roster or participant list) and never
derived from free-form text. The caller's ``query`` string is a pure
substring filter *over the resolved set* — it is not a classifier.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.model.agent.conversation.conversation import Conversation
from src.domain.ports.repositories.workspace.workspace_agent_repository import (
    WorkspaceAgentRepository,
)


@dataclass(frozen=True)
class MentionCandidate:
    """One candidate agent returned to the frontend MentionPicker."""

    agent_id: str
    display_name: str | None
    label: str | None
    status: str
    is_active: bool
    source: str  # "workspace" or "conversation"


class WorkspaceMentionCandidatesResolver:
    """Resolve mention candidates for a conversation.

    The resolver has no side effects and does no DB commit.  Callers
    wire it up inside a request scope and feed it the already-loaded
    :class:`Conversation`.
    """

    def __init__(self, workspace_agent_repository: WorkspaceAgentRepository) -> None:
        self._workspace_agent_repository = workspace_agent_repository

    async def resolve(
        self,
        conversation: Conversation,
        *,
        include_inactive: bool = False,
    ) -> list[MentionCandidate]:
        workspace_id = getattr(conversation, "workspace_id", None)
        if workspace_id:
            agents = await self._workspace_agent_repository.find_by_workspace(
                workspace_id,
                active_only=not include_inactive,
            )
            return [
                MentionCandidate(
                    agent_id=agent.agent_id,
                    display_name=agent.display_name,
                    label=agent.label,
                    status=agent.status,
                    is_active=agent.is_active,
                    source="workspace",
                )
                for agent in agents
            ]

        return [
            MentionCandidate(
                agent_id=agent_id,
                display_name=None,
                label=None,
                status="idle",
                is_active=True,
                source="conversation",
            )
            for agent_id in conversation.participant_agents
        ]
