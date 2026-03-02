"""Host-side tool executor for tools that must run on the host machine.

A thin pass-through executor for host-only tools. Exists for symmetry
with SandboxToolExecutor and to provide a hook for future instrumentation
(logging, metrics, permission checks).
"""

from __future__ import annotations

import logging

from src.infrastructure.agent.core.tool_execution_router import ToolExecutionConfig
from src.infrastructure.agent.tools.define import ToolInfo

logger = logging.getLogger(__name__)


class HostToolExecutor:
    """Pass-through executor for host-only tools.

    Host tools execute directly in the agent process. This executor
    returns the ToolInfo unchanged, providing a symmetric interface
    with SandboxToolExecutor.
    """

    def wrap(self, tool_info: ToolInfo, config: ToolExecutionConfig) -> ToolInfo:
        """Return the tool unchanged (host execution needs no wrapping).

        Args:
            tool_info: The original tool definition.
            config: Execution configuration (unused for host tools).

        Returns:
            The original ToolInfo, unmodified.
        """
        return tool_info
