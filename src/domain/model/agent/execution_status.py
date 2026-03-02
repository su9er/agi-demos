"""Backward compatibility - re-exports from execution subpackage."""

from src.domain.model.agent.execution.execution_status import (
    AgentExecution,
    AgentExecutionStatus,
)

__all__ = [
    "AgentExecution",
    "AgentExecutionStatus",
]
