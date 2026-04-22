"""Workspace-roster validator for ``Conversation.participant_agents`` (G4).

When a :class:`Conversation` is linked to a :class:`Workspace` via
``workspace_id`` (G2), its ``participant_agents`` roster MUST be a
subset of the workspace's active :class:`WorkspaceAgent` bindings.  This
invariant is enforced at the application layer because it spans two
aggregates (Conversation + WorkspaceAgent) and needs the repository to
resolve membership.

Agent First: set-membership only — no content inspection, no semantic
inference.  The validator returns either ``None`` (valid) or raises a
:class:`ParticipantNotPresentError` naming the offending agent ids.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.model.agent.conversation.errors import ParticipantNotPresentError

if TYPE_CHECKING:
    from src.domain.model.agent.conversation.conversation import Conversation
    from src.domain.ports.repositories.workspace.workspace_agent_repository import (
        WorkspaceAgentRepository,
    )


class WorkspaceRosterValidator:
    """Validate that a conversation's roster is a subset of its workspace."""

    def __init__(self, *, workspace_agent_repository: WorkspaceAgentRepository) -> None:
        self._agents = workspace_agent_repository

    async def assert_valid(self, conversation: Conversation) -> None:
        """Raise :class:`ParticipantNotPresentError` if any participant is
        not bound to the conversation's workspace.

        No-op when ``workspace_id`` is unset (workspace-less conversations
        do not have a roster to subset against) or ``participant_agents``
        is empty.
        """
        workspace_id = conversation.workspace_id
        if not workspace_id:
            return
        if not conversation.participant_agents:
            return

        roster = await self._load_roster(workspace_id)
        missing = [aid for aid in conversation.participant_agents if aid not in roster]
        if missing:
            joined = ", ".join(sorted(set(missing)))
            raise ParticipantNotPresentError(
                f"participant_agents not in workspace {workspace_id} roster: {joined}"
            )

    async def _load_roster(self, workspace_id: str) -> set[str]:
        bindings = await self._agents.find_by_workspace(
            workspace_id=workspace_id, active_only=True, limit=1000, offset=0
        )
        return {binding.agent_id for binding in bindings}


__all__ = ["WorkspaceRosterValidator"]
