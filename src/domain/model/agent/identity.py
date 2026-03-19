"""AgentIdentity value object — immutable snapshot of an agent's configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.model.agent.spawn_policy import SpawnPolicy
from src.domain.model.agent.subagent import AgentModel
from src.domain.model.agent.tool_policy import ToolPolicy
from src.domain.shared_kernel import ValueObject


@dataclass(frozen=True)
class AgentIdentity(ValueObject):
    agent_id: str
    name: str
    description: str = ""
    system_prompt: str = ""
    model: AgentModel = AgentModel.INHERIT
    allowed_tools: tuple[str, ...] = ()
    allowed_skills: tuple[str, ...] = ()
    spawn_policy: SpawnPolicy = field(default_factory=SpawnPolicy)
    tool_policy: ToolPolicy = field(default_factory=ToolPolicy)
    metadata: tuple[tuple[str, str], ...] = ()
