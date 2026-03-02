"""Unit tests for the LLM model failover chain."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.infrastructure.llm.failover_chain import (
    FailoverChain,
    FailoverConfig,
    FailoverResult,
    ProviderHealth,
    is_failover_worthy,
)

SEQUENCE = [
    ("gemini", "gemini-2.0-flash"),
    ("openai", "gpt-4o"),
    ("deepseek", "deepseek-chat"),
]


class _StatusError(Exception):
    """Test helper: exception carrying an HTTP status code."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@pytest.mark.unit
class TestFailoverConfig:
    def test_defaults(self) -> None:
        cfg = FailoverConfig()
        assert cfg.max_failover_attempts == 3
        assert cfg.failover_timeout_seconds == 30.0
        assert cfg.track_provider_health is True
        assert cfg.cooldown_seconds == 60.0

    def test_frozen(self) -> None:
        cfg = FailoverConfig()
        with pytest.raises(AttributeError):
            cfg.max_failover_attempts = 10


@pytest.mark.unit
class TestProviderHealth:
    def test_defaults(self) -> None:
        health = ProviderHealth(provider="openai", model="gpt-4o")
        assert health.consecutive_failures == 0
        assert health.last_failure_at is None
        assert health.is_healthy is True

    def test_mutable(self) -> None:
        health = ProviderHealth(provider="openai", model="gpt-4o")
        health.consecutive_failures = 3
        health.is_healthy = False
        assert health.consecutive_failures == 3
        assert health.is_healthy is False


@pytest.mark.unit
class TestFailoverResult:
    def test_success_result(self) -> None:
        result = FailoverResult(
            success=True,
            provider_used="openai",
            model_used="gpt-4o",
            attempts=[{"provider": "openai", "success": True}],
            total_duration_ms=50.0,
            response={"content": "hello"},
        )
        assert result.success is True
        assert result.response == {"content": "hello"}

    def test_failure_result(self) -> None:
        result = FailoverResult(
            success=False,
            provider_used="openai",
            model_used="gpt-4o",
            attempts=[],
            total_duration_ms=100.0,
        )
        assert result.success is False
        assert result.response is None


@pytest.mark.unit
class TestIsFailoverWorthy:
    def test_rate_limit_429(self) -> None:
        err = _StatusError("rate limit exceeded", status_code=429)
        assert is_failover_worthy(err) is True

    def test_server_error_500(self) -> None:
        err = _StatusError("internal server error", status_code=500)
        assert is_failover_worthy(err) is True

    def test_bad_gateway_502(self) -> None:
        err = _StatusError("bad gateway", status_code=502)
        assert is_failover_worthy(err) is True

    def test_service_unavailable_503(self) -> None:
        err = _StatusError("service unavailable", status_code=503)
        assert is_failover_worthy(err) is True

    def test_gateway_timeout_504(self) -> None:
        err = _StatusError("gateway timeout", status_code=504)
        assert is_failover_worthy(err) is True

    def test_auth_error_401_not_failover(self) -> None:
        err = _StatusError("unauthorized", status_code=401)
        assert is_failover_worthy(err) is False

    def test_forbidden_403_not_failover(self) -> None:
        err = _StatusError("forbidden", status_code=403)
        assert is_failover_worthy(err) is False

    def test_rate_limit_message_pattern(self) -> None:
        err = Exception("Rate limit exceeded, please retry later")
        assert is_failover_worthy(err) is True

    def test_timeout_message_pattern(self) -> None:
        err = Exception("Request timed out after 30s")
        assert is_failover_worthy(err) is True

    def test_connection_error_message_pattern(self) -> None:
        err = Exception("Connection refused to host")
        assert is_failover_worthy(err) is True

    def test_auth_message_pattern_not_failover(self) -> None:
        err = Exception("Invalid API key provided")
        assert is_failover_worthy(err) is False

    def test_context_too_long_not_failover(self) -> None:
        err = Exception("Context length exceeded maximum of 128000 tokens")
        assert is_failover_worthy(err) is False

    def test_validation_error_not_failover(self) -> None:
        err = Exception("Validation error: invalid request format")
        assert is_failover_worthy(err) is False

    def test_timeout_error_type(self) -> None:
        class TimeoutError(Exception):
            pass

        err = TimeoutError("something")
        assert is_failover_worthy(err) is True

    def test_connection_error_type(self) -> None:
        class ConnectionError(Exception):
            pass

        err = ConnectionError("something")
        assert is_failover_worthy(err) is True

    def test_unknown_error_not_failover(self) -> None:
        err = ValueError("some random value error")
        assert is_failover_worthy(err) is False


@pytest.mark.unit
class TestFailoverChainInit:
    def test_empty_sequence_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one entry"):
            FailoverChain(fallback_sequence=[])

    def test_default_config(self) -> None:
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        assert chain.config.max_failover_attempts == 3

    def test_custom_config(self) -> None:
        cfg = FailoverConfig(max_failover_attempts=5)
        chain = FailoverChain(fallback_sequence=SEQUENCE, config=cfg)
        assert chain.config.max_failover_attempts == 5

    def test_fallback_sequence_copy(self) -> None:
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        seq = chain.fallback_sequence
        seq.append(("extra", "extra-model"))
        assert len(chain.fallback_sequence) == 3


@pytest.mark.unit
class TestFailoverChainExecute:
    async def test_success_first_try(self) -> None:
        # Arrange
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        call_fn = AsyncMock(return_value={"content": "hello"})

        # Act
        result = await chain.execute(call_fn)

        # Assert
        assert result.success is True
        assert result.provider_used == "gemini"
        assert result.model_used == "gemini-2.0-flash"
        assert result.response == {"content": "hello"}
        assert len(result.attempts) == 1
        assert result.attempts[0]["success"] is True
        call_fn.assert_called_once_with("gemini", "gemini-2.0-flash")

    async def test_failover_to_second_on_rate_limit(self) -> None:
        # Arrange
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        call_fn = AsyncMock(
            side_effect=[
                _StatusError("rate limited", status_code=429),
                {"content": "from openai"},
            ]
        )

        # Act
        result = await chain.execute(call_fn)

        # Assert
        assert result.success is True
        assert result.provider_used == "openai"
        assert result.model_used == "gpt-4o"
        assert result.response == {"content": "from openai"}
        assert len(result.attempts) == 2
        assert result.attempts[0]["success"] is False
        assert result.attempts[1]["success"] is True

    async def test_failover_to_third_when_first_two_fail(self) -> None:
        # Arrange
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        call_fn = AsyncMock(
            side_effect=[
                _StatusError("server error", status_code=500),
                Exception("Connection refused to endpoint"),
                {"content": "from deepseek"},
            ]
        )

        # Act
        result = await chain.execute(call_fn)

        # Assert
        assert result.success is True
        assert result.provider_used == "deepseek"
        assert result.model_used == "deepseek-chat"
        assert len(result.attempts) == 3

    async def test_max_attempts_exceeded(self) -> None:
        # Arrange
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        call_fn = AsyncMock(side_effect=_StatusError("overloaded", status_code=503))

        # Act
        result = await chain.execute(call_fn)

        # Assert
        assert result.success is False
        assert len(result.attempts) == 3
        assert all(not a["success"] for a in result.attempts)

    async def test_auth_error_stops_immediately(self) -> None:
        # Arrange
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        call_fn = AsyncMock(side_effect=_StatusError("unauthorized", status_code=401))

        # Act
        result = await chain.execute(call_fn)

        # Assert
        assert result.success is False
        assert len(result.attempts) == 1
        assert result.provider_used == "gemini"

    async def test_context_too_long_stops_immediately(self) -> None:
        # Arrange
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        call_fn = AsyncMock(
            side_effect=Exception("Context length exceeded maximum of 128000 tokens")
        )

        # Act
        result = await chain.execute(call_fn)

        # Assert
        assert result.success is False
        assert len(result.attempts) == 1

    async def test_forwards_extra_args(self) -> None:
        # Arrange
        chain = FailoverChain(fallback_sequence=[("openai", "gpt-4o")])
        call_fn = AsyncMock(return_value="ok")

        # Act
        await chain.execute(call_fn, "extra_arg", key="value")

        # Assert
        call_fn.assert_called_once_with("openai", "gpt-4o", "extra_arg", key="value")

    async def test_max_attempts_capped_by_sequence_length(self) -> None:
        # Arrange -- config allows 10 attempts but only 2 providers
        cfg = FailoverConfig(max_failover_attempts=10)
        chain = FailoverChain(
            fallback_sequence=[
                ("openai", "gpt-4o"),
                ("gemini", "gemini-2.0-flash"),
            ],
            config=cfg,
        )
        call_fn = AsyncMock(side_effect=_StatusError("overloaded", status_code=503))

        # Act
        result = await chain.execute(call_fn)

        # Assert
        assert len(result.attempts) == 2

    async def test_timeout_budget_respected(self) -> None:
        # Arrange -- very tight timeout
        cfg = FailoverConfig(
            failover_timeout_seconds=0.0,
            max_failover_attempts=3,
        )
        chain = FailoverChain(fallback_sequence=SEQUENCE, config=cfg)
        call_fn = AsyncMock(side_effect=_StatusError("timeout", status_code=504))

        # Act
        result = await chain.execute(call_fn)

        # Assert -- should stop early due to timeout
        assert result.success is False
        assert len(result.attempts) <= 1

    async def test_result_tracks_duration(self) -> None:
        # Arrange
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        call_fn = AsyncMock(return_value="ok")

        # Act
        result = await chain.execute(call_fn)

        # Assert
        assert result.total_duration_ms >= 0
        assert result.attempts[0]["duration_ms"] >= 0


@pytest.mark.unit
class TestFailoverChainHealth:
    def test_new_provider_is_healthy(self) -> None:
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        assert chain.is_provider_healthy("gemini", "gemini-2.0-flash") is True

    def test_mark_failed_makes_unhealthy(self) -> None:
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        chain.mark_provider_failed("gemini", "gemini-2.0-flash")
        assert chain.is_provider_healthy("gemini", "gemini-2.0-flash") is False

    def test_mark_recovered_restores_health(self) -> None:
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        chain.mark_provider_failed("gemini", "gemini-2.0-flash")
        chain.mark_provider_recovered("gemini", "gemini-2.0-flash")
        assert chain.is_provider_healthy("gemini", "gemini-2.0-flash") is True

    def test_consecutive_failures_tracked(self) -> None:
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        chain.mark_provider_failed("openai", "gpt-4o")
        chain.mark_provider_failed("openai", "gpt-4o")
        chain.mark_provider_failed("openai", "gpt-4o")

        health = chain.get_provider_health("openai", "gpt-4o")
        assert health is not None
        assert health.consecutive_failures == 3

    def test_recovery_resets_failures(self) -> None:
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        chain.mark_provider_failed("openai", "gpt-4o")
        chain.mark_provider_failed("openai", "gpt-4o")
        chain.mark_provider_recovered("openai", "gpt-4o")

        health = chain.get_provider_health("openai", "gpt-4o")
        assert health is not None
        assert health.consecutive_failures == 0
        assert health.last_failure_at is None

    def test_cooldown_expiry_restores_health(self) -> None:
        # Arrange -- very short cooldown
        cfg = FailoverConfig(cooldown_seconds=0.0)
        chain = FailoverChain(fallback_sequence=SEQUENCE, config=cfg)
        chain.mark_provider_failed("gemini", "gemini-2.0-flash")

        # Act -- cooldown_seconds=0 means immediate expiry
        is_healthy = chain.is_provider_healthy("gemini", "gemini-2.0-flash")

        # Assert
        assert is_healthy is True

    def test_is_provider_healthy_without_model_checks_all(self) -> None:
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        chain.mark_provider_failed("gemini", "gemini-2.0-flash")
        assert chain.is_provider_healthy("gemini") is False

    def test_unknown_provider_is_healthy(self) -> None:
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        assert chain.is_provider_healthy("unknown_provider") is True


@pytest.mark.unit
class TestGetHealthySequence:
    def test_all_healthy_returns_full_sequence(self) -> None:
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        healthy = chain.get_healthy_sequence()
        assert healthy == SEQUENCE

    def test_filters_unhealthy_providers(self) -> None:
        cfg = FailoverConfig(cooldown_seconds=600.0)
        chain = FailoverChain(fallback_sequence=SEQUENCE, config=cfg)
        chain.mark_provider_failed("gemini", "gemini-2.0-flash")

        healthy = chain.get_healthy_sequence()
        assert len(healthy) == 2
        assert ("gemini", "gemini-2.0-flash") not in healthy
        assert ("openai", "gpt-4o") in healthy
        assert ("deepseek", "deepseek-chat") in healthy

    def test_health_tracking_disabled_returns_full(self) -> None:
        cfg = FailoverConfig(track_provider_health=False)
        chain = FailoverChain(fallback_sequence=SEQUENCE, config=cfg)
        chain.mark_provider_failed("gemini", "gemini-2.0-flash")

        healthy = chain.get_healthy_sequence()
        assert healthy == SEQUENCE

    async def test_execute_skips_unhealthy_provider(self) -> None:
        # Arrange
        cfg = FailoverConfig(cooldown_seconds=600.0)
        chain = FailoverChain(fallback_sequence=SEQUENCE, config=cfg)
        chain.mark_provider_failed("gemini", "gemini-2.0-flash")

        call_fn = AsyncMock(return_value={"content": "ok"})

        # Act
        result = await chain.execute(call_fn)

        # Assert -- should skip gemini and go straight to openai
        assert result.success is True
        assert result.provider_used == "openai"
        assert result.model_used == "gpt-4o"
        call_fn.assert_called_once_with("openai", "gpt-4o")

    async def test_all_unhealthy_falls_back_to_full(self) -> None:
        # Arrange
        cfg = FailoverConfig(cooldown_seconds=600.0)
        chain = FailoverChain(fallback_sequence=SEQUENCE, config=cfg)
        for provider, model in SEQUENCE:
            chain.mark_provider_failed(provider, model)

        call_fn = AsyncMock(return_value={"content": "ok"})

        # Act
        result = await chain.execute(call_fn)

        # Assert -- falls back to full sequence when all unhealthy
        assert result.success is True
        assert result.provider_used == "gemini"

    async def test_execute_updates_health_on_success(self) -> None:
        # Arrange
        cfg = FailoverConfig(cooldown_seconds=600.0)
        chain = FailoverChain(fallback_sequence=SEQUENCE, config=cfg)
        chain.mark_provider_failed("gemini", "gemini-2.0-flash")

        call_fn = AsyncMock(return_value={"content": "ok"})

        # Act
        result = await chain.execute(call_fn)

        # Assert
        assert result.success is True
        health = chain.get_provider_health("openai", "gpt-4o")
        assert health is not None
        assert health.is_healthy is True

    async def test_execute_updates_health_on_failure(self) -> None:
        # Arrange
        chain = FailoverChain(fallback_sequence=SEQUENCE)
        call_fn = AsyncMock(side_effect=_StatusError("overloaded", status_code=503))

        # Act
        await chain.execute(call_fn)

        # Assert -- all providers should be marked failed
        for provider, model in SEQUENCE:
            health = chain.get_provider_health(provider, model)
            assert health is not None
            assert health.is_healthy is False
            assert health.consecutive_failures == 1
