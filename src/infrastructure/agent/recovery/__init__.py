"""Session recovery module for agent error detection and recovery.

Provides error classification, recovery strategies, and orchestration
for recovering from various failure modes during agent execution.
"""

from __future__ import annotations

from .error_classifier import ErrorClassifier, ErrorType
from .recovery_strategy import (
    AbortWithMessageStrategy,
    BreakLoopStrategy,
    CompactContextStrategy,
    ProviderFailoverStrategy,
    RecoveryStrategy,
    ResetToolStateStrategy,
    RetryWithBackoffStrategy,
)
from .session_recovery_service import RecoveryResult, SessionRecoveryService

__all__ = [
    "AbortWithMessageStrategy",
    "BreakLoopStrategy",
    "CompactContextStrategy",
    "ErrorClassifier",
    "ErrorType",
    "ProviderFailoverStrategy",
    "RecoveryResult",
    "RecoveryStrategy",
    "ResetToolStateStrategy",
    "RetryWithBackoffStrategy",
    "SessionRecoveryService",
]
