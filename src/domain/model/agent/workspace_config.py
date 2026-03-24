"""
Workspace configuration for agent isolated environments.

Defines per-agent workspace settings including storage limits,
persona files, and cleanup policies.
"""

from dataclasses import dataclass, field
from typing import Any

from src.domain.model.agent.sandbox_scope import SandboxScope

_FRONTEND_TYPE_TO_SCOPE: dict[str, str] = {
    "shared": SandboxScope.SHARED.value,
    "isolated": SandboxScope.AGENT.value,
    "inherited": SandboxScope.SESSION.value,
}


@dataclass
class WorkspaceConfig:
    """Configuration for an agent's isolated workspace.

    Workspace serves as:
    - Long-term memory (files persist across sessions)
    - Shared context (AGENTS.md, SOUL.md, USER.md)
    - Artifact storage

    Attributes:
        base_path: Workspace root path (e.g., ".memstack/agents/{agent_name}/")
        max_size_mb: Maximum workspace size in megabytes
        persona_files: Persona definition files to inject into system prompt
        shared_files: Files shared with spawned sub-agents
        auto_cleanup: Whether to auto-clean old files
        retention_days: Days to retain files when auto_cleanup is enabled
    """

    base_path: str = ""
    max_size_mb: int = 100
    persona_files: list[str] = field(default_factory=list)
    shared_files: list[str] = field(default_factory=list)
    auto_cleanup: bool = False
    retention_days: int = 30
    sandbox_scope: SandboxScope = SandboxScope.AGENT

    def __post_init__(self) -> None:
        """Validate the workspace config."""
        if self.max_size_mb < 0:
            raise ValueError("max_size_mb must be non-negative")
        if self.retention_days < 1:
            raise ValueError("retention_days must be at least 1")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "base_path": self.base_path,
            "max_size_mb": self.max_size_mb,
            "persona_files": list(self.persona_files),
            "shared_files": list(self.shared_files),
            "auto_cleanup": self.auto_cleanup,
            "retention_days": self.retention_days,
            "sandbox_scope": self.sandbox_scope.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkspaceConfig":
        """Create from dictionary.

        Accepts both backend-native keys and frontend alias keys:
        - ``sandbox_scope`` (backend) or ``type`` (frontend) for sandbox scope
        - ``base_path`` (backend) or ``base_dir`` (frontend) for workspace root

        Backend-native keys take precedence when both are present.
        """
        # Resolve sandbox scope: prefer backend key, fall back to frontend alias
        if "sandbox_scope" in data:
            raw_scope = data["sandbox_scope"]
        elif "type" in data and data["type"] in _FRONTEND_TYPE_TO_SCOPE:
            raw_scope = _FRONTEND_TYPE_TO_SCOPE[data["type"]]
        else:
            raw_scope = SandboxScope.AGENT.value

        scope = SandboxScope(raw_scope) if isinstance(raw_scope, str) else raw_scope

        # Resolve base path: prefer backend key, fall back to frontend alias
        base_path = data.get("base_path") or data.get("base_dir", "")

        return cls(
            base_path=base_path,
            max_size_mb=data.get("max_size_mb", 100),
            persona_files=data.get("persona_files", []),
            shared_files=data.get("shared_files", []),
            auto_cleanup=data.get("auto_cleanup", False),
            retention_days=data.get("retention_days", 30),
            sandbox_scope=scope,
        )

    @classmethod
    def default(cls) -> "WorkspaceConfig":
        """Create a default workspace config."""
        return cls()
