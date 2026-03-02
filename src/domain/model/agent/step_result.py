"""Backward compatibility - re-exports from execution subpackage."""

from src.domain.model.agent.execution.step_result import (
    StepOutcome,
    StepResult,
)

__all__ = [
    "StepOutcome",
    "StepResult",
]
