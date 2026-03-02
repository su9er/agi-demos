"""Unit tests for ErrorClassifier."""

from __future__ import annotations

import pytest

from src.infrastructure.agent.errors import (
    AgentCommunicationError,
    AgentExecutionError,
    AgentPermissionError,
    AgentResourceError,
    AgentTimeoutError,
)
from src.infrastructure.agent.recovery.error_classifier import (
    ErrorClassifier,
    ErrorType,
)


@pytest.mark.unit
class TestErrorClassifier:
    """Tests for ErrorClassifier.classify()."""

    def setup_method(self) -> None:
        """Create a fresh classifier for each test."""
        self.classifier = ErrorClassifier()  # pyright: ignore[reportUninitializedInstanceVariable]

    # -- Error code classification --

    def test_classify_doom_loop_by_error_code(self) -> None:
        """Classify error with code='DOOM_LOOP_DETECTED' as DOOM_LOOP."""
        # Arrange
        error = Exception("stuck")
        error.code = "DOOM_LOOP_DETECTED"  # type: ignore[attr-defined]

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.DOOM_LOOP

    def test_classify_tool_timeout_by_error_code(self) -> None:
        """Classify error with code='TOOL_TIMEOUT' as TOOL_TIMEOUT."""
        # Arrange
        error = Exception("timed out")
        error.code = "TOOL_TIMEOUT"  # type: ignore[attr-defined]

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.TOOL_TIMEOUT

    def test_classify_timeout_code_variant(self) -> None:
        """Classify error with code='TIMEOUT' as TOOL_TIMEOUT."""
        # Arrange
        error = Exception("operation timed out")
        error.code = "TIMEOUT"  # type: ignore[attr-defined]

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.TOOL_TIMEOUT

    def test_classify_tool_execution_error_by_code(self) -> None:
        """Classify error with code='TOOL_EXECUTION_ERROR'."""
        # Arrange
        error = Exception("tool failed")
        error.code = "TOOL_EXECUTION_ERROR"  # type: ignore[attr-defined]

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.TOOL_EXECUTION_ERROR

    # -- AgentError subclass classification --

    def test_classify_agent_timeout_tool(self) -> None:
        """Classify AgentTimeoutError with tool operation as TOOL_TIMEOUT."""
        # Arrange
        error = AgentTimeoutError(
            message="Tool execution timed out",
            operation="tool_execute",
        )

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.TOOL_TIMEOUT

    def test_classify_agent_timeout_llm(self) -> None:
        """Classify AgentTimeoutError without tool operation as LLM_PROVIDER_DOWN."""
        # Arrange
        error = AgentTimeoutError(
            message="LLM request timed out",
            operation="llm_invoke",
        )

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_PROVIDER_DOWN

    def test_classify_agent_execution_error_with_tool(self) -> None:
        """Classify AgentExecutionError with tool_name as TOOL_EXECUTION_ERROR."""
        # Arrange
        error = AgentExecutionError(
            message="Tool crashed",
            tool_name="terminal",
        )

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.TOOL_EXECUTION_ERROR

    def test_classify_agent_execution_error_without_tool(self) -> None:
        """Classify AgentExecutionError without tool_name as TOOL_EXECUTION_ERROR."""
        # Arrange
        error = AgentExecutionError(message="Execution failed")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.TOOL_EXECUTION_ERROR

    def test_classify_agent_communication_error_rate_limit(self) -> None:
        """Classify AgentCommunicationError with 429 as LLM_RATE_LIMIT."""
        # Arrange
        error = AgentCommunicationError(
            message="Rate limited",
            status_code=429,
        )

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_RATE_LIMIT

    def test_classify_agent_communication_error_server(self) -> None:
        """Classify AgentCommunicationError with 500 as LLM_PROVIDER_DOWN."""
        # Arrange
        error = AgentCommunicationError(
            message="Internal server error",
            status_code=500,
        )

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_PROVIDER_DOWN

    def test_classify_agent_communication_error_no_status(self) -> None:
        """Classify AgentCommunicationError without status as LLM_PROVIDER_DOWN."""
        # Arrange
        error = AgentCommunicationError(message="Connection failed")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_PROVIDER_DOWN

    def test_classify_agent_resource_error_context(self) -> None:
        """Classify AgentResourceError for context as LLM_CONTEXT_OVERFLOW."""
        # Arrange
        error = AgentResourceError(
            message="Context window exceeded",
            resource_type="context",
        )

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_CONTEXT_OVERFLOW

    def test_classify_agent_resource_error_token(self) -> None:
        """Classify AgentResourceError for token as LLM_CONTEXT_OVERFLOW."""
        # Arrange
        error = AgentResourceError(
            message="Token limit exceeded",
            resource_type="token",
        )

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_CONTEXT_OVERFLOW

    def test_classify_agent_resource_error_generic(self) -> None:
        """Classify AgentResourceError without resource type as LLM_RATE_LIMIT."""
        # Arrange
        error = AgentResourceError(message="Resource exhausted")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_RATE_LIMIT

    def test_classify_agent_permission_error(self) -> None:
        """Classify AgentPermissionError as LLM_AUTH_ERROR."""
        # Arrange
        error = AgentPermissionError(
            message="Permission denied",
            action="execute",
        )

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_AUTH_ERROR

    # -- HTTP status code classification --

    def test_classify_by_status_code_429(self) -> None:
        """Classify generic exception with status_code=429 as LLM_RATE_LIMIT."""
        # Arrange
        error = Exception("Rate limited")
        error.status_code = 429  # type: ignore[attr-defined]

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_RATE_LIMIT

    def test_classify_by_status_code_401(self) -> None:
        """Classify generic exception with status_code=401 as LLM_AUTH_ERROR."""
        # Arrange
        error = Exception("Unauthorized")
        error.status_code = 401  # type: ignore[attr-defined]

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_AUTH_ERROR

    def test_classify_by_status_code_403(self) -> None:
        """Classify generic exception with status_code=403 as LLM_AUTH_ERROR."""
        # Arrange
        error = Exception("Forbidden")
        error.status_code = 403  # type: ignore[attr-defined]

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_AUTH_ERROR

    def test_classify_by_status_code_502(self) -> None:
        """Classify generic exception with status_code=502 as LLM_PROVIDER_DOWN."""
        # Arrange
        error = Exception("Bad Gateway")
        error.status_code = 502  # type: ignore[attr-defined]

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_PROVIDER_DOWN

    def test_classify_by_status_code_503(self) -> None:
        """Classify generic exception with status_code=503 as LLM_PROVIDER_DOWN."""
        # Arrange
        error = Exception("Service Unavailable")
        error.status_code = 503  # type: ignore[attr-defined]

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_PROVIDER_DOWN

    # -- Message pattern classification --

    def test_classify_rate_limit_by_message(self) -> None:
        """Classify 'rate limit exceeded' message as LLM_RATE_LIMIT."""
        # Arrange
        error = Exception("Error: rate limit exceeded, please retry later")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_RATE_LIMIT

    def test_classify_too_many_requests_by_message(self) -> None:
        """Classify 'too many requests' message as LLM_RATE_LIMIT."""
        # Arrange
        error = Exception("too many requests from this IP")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_RATE_LIMIT

    def test_classify_context_overflow_by_message(self) -> None:
        """Classify 'context length exceeded' message as LLM_CONTEXT_OVERFLOW."""
        # Arrange
        error = Exception("This model's context length is 4096 tokens")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_CONTEXT_OVERFLOW

    def test_classify_token_limit_by_message(self) -> None:
        """Classify 'token limit' message as LLM_CONTEXT_OVERFLOW."""
        # Arrange
        error = Exception("Error: token limit reached")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_CONTEXT_OVERFLOW

    def test_classify_provider_down_by_message(self) -> None:
        """Classify 'service unavailable' message as LLM_PROVIDER_DOWN."""
        # Arrange
        error = Exception("The service is temporarily unavailable")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_PROVIDER_DOWN

    def test_classify_auth_by_message(self) -> None:
        """Classify 'invalid api key' message as LLM_AUTH_ERROR."""
        # Arrange
        error = Exception("invalid api key provided")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_AUTH_ERROR

    def test_classify_doom_loop_by_message(self) -> None:
        """Classify 'stuck in a loop' message as DOOM_LOOP."""
        # Arrange
        error = Exception("Agent appears stuck in a loop")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.DOOM_LOOP

    def test_classify_sandbox_by_message(self) -> None:
        """Classify 'sandbox error' message as SANDBOX_ERROR."""
        # Arrange
        error = Exception("Sandbox container failed to start")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.SANDBOX_ERROR

    def test_classify_unknown_error(self) -> None:
        """Classify unrecognized error as UNKNOWN."""
        # Arrange
        error = Exception("Something completely unexpected happened")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.UNKNOWN

    # -- Timeout type name detection --

    def test_classify_timeout_exception_type_name(self) -> None:
        """Classify exception with 'timeout' in type name as TOOL_TIMEOUT."""

        # Arrange
        class CustomTimeoutError(Exception):
            pass

        error = CustomTimeoutError("timed out")

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.TOOL_TIMEOUT

    # -- Nested response status code --

    def test_classify_nested_response_status_code(self) -> None:
        """Classify error with nested response.status_code."""

        # Arrange
        class FakeResponse:
            status_code = 429

        error = Exception("Something went wrong")
        error.response = FakeResponse()  # type: ignore[attr-defined]

        # Act
        result = self.classifier.classify(error)

        # Assert
        assert result == ErrorType.LLM_RATE_LIMIT
