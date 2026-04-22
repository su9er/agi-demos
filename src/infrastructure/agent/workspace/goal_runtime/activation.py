"""Workspace authority activation rules + decomposer Protocol.

``should_activate_workspace_authority`` decides whether a given turn
triggers the workspace autonomy codepath. Extracted from the original
``workspace_goal_runtime`` God module so the activation gate is
independently testable and re-usable by the V2 orchestrator.

Agent-First iron rule (AGENTS.md): this gate uses only **structural
set-membership signals** (binding marker presence, open-root existence).
Semantic classification of the user query lives in the sensing service,
which delegates the verdict to an agent tool-call.
"""

from __future__ import annotations

import re
from typing import Protocol

from src.infrastructure.agent.subagent.task_decomposer import DecompositionResult

# Retained for structural ID extraction by callers (reads a named ID field
# from text — analogous to reading a JSON field; allowed under Agent-First).
_WORKSPACE_TASK_ID_PATTERN = re.compile(
    r"(?:workspace_task_id|task_id|child_task_id)\s*[:=]\s*([A-Za-z0-9._-]+)",
    re.IGNORECASE,
)


def should_activate_workspace_authority(
    user_query: str,  # reserved for future structured-signal use; never parsed
    *,
    has_workspace_binding: bool = False,
    has_open_root: bool = False,
) -> bool:
    """Decide whether to run workspace autonomy for this turn.

    Agent-First iron rule (AGENTS.md): semantic verdicts must come from an
    agent tool-call. This gate is driven only by **structural set-membership
    signals** the caller has already established:

    - ``has_workspace_binding`` — the turn carries a ``[workspace-task-binding]``
      marker (structural payload field);
    - ``has_open_root`` — the workspace has at least one open goal-root task
      (set-membership query against ``workspace_tasks``).

    ``user_query`` is **not** inspected. If a user expresses an unsolicited
    goal in chat, the sensing service's ``message_signal`` path (agent-judged)
    materializes the candidate.
    """
    return has_workspace_binding or has_open_root


class TaskDecomposerProtocol(Protocol):
    async def decompose(self, query: str) -> DecompositionResult: ...


__all__ = [
    "_WORKSPACE_TASK_ID_PATTERN",
    "TaskDecomposerProtocol",
    "should_activate_workspace_authority",
]
