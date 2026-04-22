"""Resolve the effective ``blocking_categories`` for a HITL decision.

Phase-5 Track G5. The HITL policy machinery in
``src/domain/model/agent/conversation/hitl_policy.py`` accepts
``blocking_categories`` as an input; callers must assemble the set.
When a conversation is linked to a workspace, the workspace-level
``default_blocking_categories`` should act as a *baseline* — individual
conversations cannot lower it, but may add more categories.

The resolver is a pure function so the domain rule stays testable
independently of persistence wiring.
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = ["merge_blocking_categories"]


def merge_blocking_categories(
    *,
    workspace_defaults: Iterable[str] | None,
    conversation_overrides: Iterable[str] | None,
) -> frozenset[str]:
    """Return the union of workspace defaults and conversation overrides.

    Workspace defaults act as a *floor*: a conversation can add new
    blocking categories but cannot remove a workspace-level default.
    Both arguments are optional; missing values are treated as empty.
    """
    defaults = frozenset(workspace_defaults or ())
    overrides = frozenset(conversation_overrides or ())
    return defaults | overrides
