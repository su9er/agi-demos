"""Workspace-scoped conversation termination sweeper (Phase-5 · G6).

Unified supervisor tick: for each AUTONOMOUS conversation linked to a
workspace, resolve a :class:`TerminationContext` via the Phase-5 G3
:class:`WorkspaceTerminationResolver` and archive the conversation when
its linked :class:`WorkspaceTask` has reached
:attr:`WorkspaceTaskStatus.DONE`.

Design notes:

* Scope is intentionally **narrow**: only the *goal-completed* path is
  handled here. Budget / safety gates require live counters that only
  the running agent loop has access to — the sweeper cannot synthesise
  those without racing with the loop.
* Idempotent: a conversation that is already archived (status !=
  ACTIVE) is skipped; re-running the sweep is safe.
* Agent First: no natural-language inspection. The decision is a pure
  status-enum check delegated to the G3 resolver.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.domain.model.agent import ConversationStatus
from src.domain.model.agent.conversation.conversation_mode import ConversationMode

if TYPE_CHECKING:
    from src.application.services.agent.workspace_termination_resolver import (
        WorkspaceTerminationResolver,
    )
    from src.domain.ports.repositories.agent_repository import ConversationRepository

logger = logging.getLogger(__name__)

__all__ = [
    "WorkspaceConversationSweepResult",
    "WorkspaceConversationSweeper",
]


@dataclass(frozen=True)
class WorkspaceConversationSweepResult:
    """Outcome of a single workspace sweep."""

    workspace_id: str
    scanned: int
    archived: int
    archived_conversation_ids: tuple[str, ...]


class WorkspaceConversationSweeper:
    """Archive AUTONOMOUS conversations whose linked workspace task is DONE.

    The sweeper is constructed via DI in the application layer and is
    usually invoked by :class:`WorkspaceAutonomyIdleWaker` as part of
    its periodic sweep, but it is safe to call directly (e.g. from
    an admin endpoint).
    """

    def __init__(
        self,
        *,
        conversation_repository: ConversationRepository,
        termination_resolver: WorkspaceTerminationResolver,
    ) -> None:
        self._conversations = conversation_repository
        self._resolver = termination_resolver

    async def sweep(self, workspace_id: str) -> WorkspaceConversationSweepResult:
        conversations = await self._conversations.list_by_workspace(
            workspace_id,
            mode=ConversationMode.AUTONOMOUS,
            status=ConversationStatus.ACTIVE,
            limit=500,
        )

        archived_ids: list[str] = []
        for conversation in conversations:
            ctx = await self._resolver.resolve(conversation)
            if not ctx.goal_completed_event_id:
                continue

            conversation.status = ConversationStatus.ARCHIVED
            conversation.metadata = {
                **conversation.metadata,
                "termination": {
                    "reason": "goal_completed",
                    "triggered_by": ctx.goal_completed_event_id,
                    "summary": ctx.goal_completed_summary,
                    "actor": ctx.goal_completed_actor,
                    "archived_at": datetime.now(UTC).isoformat(),
                },
            }
            conversation.updated_at = datetime.now(UTC)
            await self._conversations.save(conversation)
            archived_ids.append(conversation.id)
            logger.info(
                "workspace_conversation_sweeper.archived",
                extra={
                    "event": "workspace_conversation_sweeper.archived",
                    "workspace_id": workspace_id,
                    "conversation_id": conversation.id,
                    "triggered_by": ctx.goal_completed_event_id,
                },
            )

        return WorkspaceConversationSweepResult(
            workspace_id=workspace_id,
            scanned=len(conversations),
            archived=len(archived_ids),
            archived_conversation_ids=tuple(archived_ids),
        )
