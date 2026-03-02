"""Unified tool execution routing for sandbox-first architecture.

Routes tool execution to either host or sandbox based on per-tool
configuration. This is the central coordination point for the tool
execution layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal, Protocol

from src.infrastructure.agent.tools.define import ToolInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class ToolExecutionConfig:
    """Per-tool execution configuration.

    Attributes:
        execution_mode: Where the tool runs ("host" or "sandbox").
        sandbox_dependencies: Python packages required in sandbox.
        sandbox_tool_name: Override name for sandbox dispatch (if different from tool name).
    """

    execution_mode: Literal["host", "sandbox"]
    sandbox_dependencies: list[str] = field(default_factory=list)
    sandbox_tool_name: str | None = None


# ---------------------------------------------------------------------------
# Executor protocol (structural subtyping to avoid circular imports)
# ---------------------------------------------------------------------------


class ToolExecutorProtocol(Protocol):
    """Structural interface for tool executors.

    Both HostToolExecutor and SandboxToolExecutor satisfy this protocol.
    """

    def wrap(self, tool_info: ToolInfo, config: ToolExecutionConfig) -> ToolInfo: ...


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class ToolExecutionRouter:
    """Routes tool execution to host or sandbox based on tool metadata.

    This class wraps ToolInfo instances with execution routing logic,
    delegating to either SandboxToolExecutor or HostToolExecutor based
    on the tool's ToolExecutionConfig.
    """

    def __init__(
        self,
        sandbox_executor: ToolExecutorProtocol,
        host_executor: ToolExecutorProtocol,
    ) -> None:
        self._sandbox = sandbox_executor
        self._host = host_executor

    def wrap_tool(
        self,
        tool_info: ToolInfo,
        config: ToolExecutionConfig,
    ) -> ToolInfo:
        """Wrap a tool with execution routing.

        Args:
            tool_info: The original tool definition.
            config: Execution configuration for this tool.

        Returns:
            A new ToolInfo with execution routed to the appropriate executor.
        """
        if config.execution_mode == "sandbox":
            logger.debug("Routing tool %s to sandbox executor", tool_info.name)
            return self._sandbox.wrap(tool_info, config)
        logger.debug("Routing tool %s to host executor", tool_info.name)
        return self._host.wrap(tool_info, config)
