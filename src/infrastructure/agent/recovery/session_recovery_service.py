"""Session Recovery Service for agent error detection and recovery.

Orchestrates error classification and recovery strategy execution,
tracking recovery attempts per session to prevent infinite recovery loops.

Reference: OpenCode session recovery patterns.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.infrastructure.agent.recovery.error_classifier import ErrorClassifier, ErrorType
from src.infrastructure.agent.recovery.recovery_strategy import (
    AbortWithMessageStrategy,
    BreakLoopStrategy,
    CompactContextStrategy,
    ProviderFailoverStrategy,
    RecoveryAction,
    RecoveryContext,
    RecoveryStrategy,
    ResetToolStateStrategy,
    RetryWithBackoffStrategy,
)

logger = logging.getLogger(__name__)

MAX_RECOVERY_ATTEMPTS = 3


@dataclass(kw_only=True, frozen=True)
class RecoveryResult:
    """Result of a session recovery attempt.

    Attributes:
        recovered: Whether recovery was successful.
        strategy_used: Name of the strategy that was applied.
        message: Human-readable description of the outcome.
        should_retry: Whether the caller should retry the failed operation.
        action: The full RecoveryAction returned by the strategy.
    """

    recovered: bool
    strategy_used: str
    message: str
    should_retry: bool
    action: RecoveryAction | None = None


class SessionRecoveryService:
    """Orchestrates error classification and recovery strategy execution.

    Tracks recovery attempts per session and enforces a maximum number
    of recovery attempts to prevent infinite recovery loops.

    Example:
        service = SessionRecoveryService()
        result = await service.attempt_recovery(
            session_id="sess-123",
            error=some_exception,
            messages=[{"role": "user", "content": "hello"}],
        )
        if result.should_retry:
            # retry the failed operation
            ...
    """

    def __init__(
        self,
        classifier: ErrorClassifier | None = None,
        strategy_overrides: Mapping[ErrorType, RecoveryStrategy] | None = None,
        max_attempts: int = MAX_RECOVERY_ATTEMPTS,
    ) -> None:
        """Initialize the recovery service.

        Args:
            classifier: Error classifier instance. Defaults to ErrorClassifier().
            strategy_overrides: Override default strategies per error type.
            max_attempts: Maximum recovery attempts per session.
        """
        self._classifier = classifier or ErrorClassifier()
        self._max_attempts = max_attempts
        self._attempt_counts: dict[str, int] = {}
        self._strategies = self._build_strategy_map(strategy_overrides)

    def _build_strategy_map(
        self,
        overrides: Mapping[ErrorType, RecoveryStrategy] | None,
    ) -> dict[ErrorType, RecoveryStrategy]:
        """Build the error type to strategy mapping.

        Args:
            overrides: Optional strategy overrides per error type.

        Returns:
            Complete mapping of error types to strategies.
        """
        defaults: dict[ErrorType, RecoveryStrategy] = {
            ErrorType.LLM_RATE_LIMIT: RetryWithBackoffStrategy(),
            ErrorType.LLM_CONTEXT_OVERFLOW: CompactContextStrategy(),
            ErrorType.LLM_PROVIDER_DOWN: ProviderFailoverStrategy(),
            ErrorType.LLM_AUTH_ERROR: AbortWithMessageStrategy(),
            ErrorType.TOOL_EXECUTION_ERROR: ResetToolStateStrategy(),
            ErrorType.TOOL_TIMEOUT: RetryWithBackoffStrategy(),
            ErrorType.DOOM_LOOP: BreakLoopStrategy(),
            ErrorType.SANDBOX_ERROR: ResetToolStateStrategy(),
            ErrorType.UNKNOWN: AbortWithMessageStrategy(),
        }
        if overrides:
            defaults.update(overrides)
        return defaults

    async def attempt_recovery(
        self,
        session_id: str,
        error: Exception,
        messages: list[dict[str, Any]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        """Attempt to recover from a session error.

        Classifies the error, selects the appropriate strategy, and
        executes recovery. Tracks attempts per session to enforce
        the maximum recovery limit.

        Args:
            session_id: The active session identifier.
            error: The exception to recover from.
            messages: Current conversation messages (for context strategies).
            extra: Additional context data for the strategy.

        Returns:
            RecoveryResult with the outcome of the recovery attempt.
        """
        attempt = self._increment_attempt(session_id)
        if attempt > self._max_attempts:
            logger.warning(
                "Max recovery attempts (%d) exceeded for session=%s",
                self._max_attempts,
                session_id,
            )
            return RecoveryResult(
                recovered=False,
                strategy_used="none",
                message=(f"Max recovery attempts ({self._max_attempts}) exceeded"),
                should_retry=False,
            )

        error_type = self._classifier.classify(error)
        strategy = self._strategies.get(error_type)

        if strategy is None:
            logger.warning(
                "No strategy found for error_type=%s (session=%s)",
                error_type.value,
                session_id,
            )
            return RecoveryResult(
                recovered=False,
                strategy_used="none",
                message=f"No recovery strategy for error type: {error_type.value}",
                should_retry=False,
            )

        context = RecoveryContext(
            session_id=session_id,
            error=error,
            error_type=error_type,
            attempt=attempt,
            messages=messages or [],
            extra=extra or {},
        )

        logger.info(
            "Attempting recovery: session=%s, error_type=%s, strategy=%s, attempt=%d",
            session_id,
            error_type.value,
            strategy.name,
            attempt,
        )

        try:
            action = await strategy.execute(context)
        except Exception as strategy_error:
            logger.exception(
                "Recovery strategy '%s' failed for session=%s: %s",
                strategy.name,
                session_id,
                strategy_error,
            )
            return RecoveryResult(
                recovered=False,
                strategy_used=strategy.name,
                message=f"Recovery strategy '{strategy.name}' failed: {strategy_error}",
                should_retry=False,
            )

        if action.recovered:
            logger.info(
                "Recovery successful: session=%s, strategy=%s, message=%s",
                session_id,
                strategy.name,
                action.message,
            )
        else:
            logger.warning(
                "Recovery failed: session=%s, strategy=%s, message=%s",
                session_id,
                strategy.name,
                action.message,
            )

        return RecoveryResult(
            recovered=action.recovered,
            strategy_used=strategy.name,
            message=action.message,
            should_retry=action.should_retry,
            action=action,
        )

    def get_attempt_count(self, session_id: str) -> int:
        """Get the current recovery attempt count for a session.

        Args:
            session_id: The session identifier.

        Returns:
            The current attempt count (0 if no attempts).
        """
        return self._attempt_counts.get(session_id, 0)

    def reset_attempts(self, session_id: str) -> None:
        """Reset recovery attempt count for a session.

        Args:
            session_id: The session identifier.
        """
        _ = self._attempt_counts.pop(session_id, None)

    def get_strategies(self) -> dict[ErrorType, RecoveryStrategy]:
        """Return a copy of the current error-type-to-strategy mapping.

        Returns:
            Dictionary mapping each ErrorType to its RecoveryStrategy.
        """
        return dict(self._strategies)

    def _increment_attempt(self, session_id: str) -> int:
        """Increment and return the attempt count for a session.

        Args:
            session_id: The session identifier.

        Returns:
            The new attempt count after incrementing.
        """
        count = self._attempt_counts.get(session_id, 0) + 1
        self._attempt_counts[session_id] = count
        return count
