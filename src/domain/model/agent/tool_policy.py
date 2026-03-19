"""Tool policy value objects for controlling tool access."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.domain.shared_kernel import ValueObject


class ToolPolicyPrecedence(str, Enum):
    ALLOW_FIRST = "allow_first"
    DENY_FIRST = "deny_first"


class ControlMessageType(str, Enum):
    STEER = "steer"
    KILL = "kill"
    PAUSE = "pause"
    RESUME = "resume"


@dataclass(frozen=True)
class ToolPolicy(ValueObject):
    """Immutable allow/deny policy for tool access.

    DENY_FIRST: deny wins on conflict; unlisted tools are allowed.
    ALLOW_FIRST: allow wins on conflict; unlisted tools are allowed
    unless they appear in deny.
    """

    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()
    precedence: ToolPolicyPrecedence = ToolPolicyPrecedence.DENY_FIRST

    def is_allowed(self, tool_name: str) -> bool:
        if self.precedence == ToolPolicyPrecedence.DENY_FIRST:
            return tool_name not in self.deny

        # ALLOW_FIRST
        if tool_name in self.allow:
            return True
        return tool_name not in self.deny

    def filter_tools(self, tool_names: tuple[str, ...] | list[str]) -> list[str]:
        return [t for t in tool_names if self.is_allowed(t)]
