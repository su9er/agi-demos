"""Unit tests for HITL recovery replay."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.configuration.config import get_settings
from src.infrastructure.adapters.secondary.persistence import (
    database as database_mod,
    sql_hitl_request_repository as hitl_repo_mod,
)
from src.infrastructure.agent.actor import execution as execution_mod
from src.infrastructure.agent.actor.state import snapshot_repo as snapshot_repo_mod
from src.infrastructure.agent.core import project_react_agent as project_agent_mod
from src.infrastructure.agent.hitl import utils as hitl_utils
from src.infrastructure.agent.hitl.recovery_service import HITLRecoveryService


def _set_hitl_encryption_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "LLM_ENCRYPTION_KEY",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    get_settings.cache_clear()
    monkeypatch.setattr(hitl_utils, "_hitl_stream_encryption_service", None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recover_unprocessed_requests_replays_answered_env_var_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_hitl_encryption_env(monkeypatch)
    response_data = {"values": {"OPENAI_API_KEY": "super-secret"}, "save": True}
    request = SimpleNamespace(
        id="req-1",
        request_type=SimpleNamespace(value="env_var"),
        conversation_id="conv-1",
        message_id="msg-1",
        tenant_id="tenant-1",
        project_id="project-1",
        question="Provide key",
        options=[],
        context={},
        metadata={"hitl_type": "env_var"},
        response="[redacted env var response]",
        response_metadata=hitl_utils.seal_hitl_response_data("env_var", response_data),
    )

    repo = MagicMock()
    repo.mark_expired_requests = AsyncMock(return_value=0)
    repo.get_unprocessed_answered_requests = AsyncMock(return_value=[request])
    repo.get_stale_processing_requests = AsyncMock(return_value=[])
    repo.claim_for_processing = AsyncMock(return_value=request)

    session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = False

    continue_chat_mock = AsyncMock(
        return_value=SimpleNamespace(is_error=False, event_count=3, error_message=None)
    )

    class _FakeAgent:
        def __init__(self, config) -> None:
            self.config = config

        async def initialize(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    monkeypatch.setattr(database_mod, "async_session_factory", lambda: session_cm)
    monkeypatch.setattr(hitl_repo_mod, "SqlHITLRequestRepository", lambda _session: repo)
    monkeypatch.setattr(execution_mod, "continue_project_chat", continue_chat_mock)
    monkeypatch.setattr(project_agent_mod, "ProjectReActAgent", _FakeAgent)
    monkeypatch.setattr(
        snapshot_repo_mod, "load_hitl_snapshot_agent_mode", AsyncMock(return_value="plan")
    )

    service = HITLRecoveryService()
    recovered = await service.recover_unprocessed_requests()

    assert recovered == 1
    repo.claim_for_processing.assert_awaited_once_with("req-1", lease_owner=service._lease_owner)
    continue_chat_mock.assert_awaited_once()
    _, call_args = continue_chat_mock.await_args
    assert continue_chat_mock.await_args.args[1] == "req-1"
    assert continue_chat_mock.await_args.args[2] == response_data
    assert call_args["lease_owner"] == service._lease_owner
    assert call_args["tenant_id"] == "tenant-1"
    assert call_args["project_id"] == "project-1"
    assert call_args["conversation_id"] == "conv-1"
    assert call_args["message_id"] == "msg-1"
    assert continue_chat_mock.await_args.args[0].config.agent_mode == "plan"

    get_settings.cache_clear()
    monkeypatch.setattr(hitl_utils, "_hitl_stream_encryption_service", None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recovery_reverts_processing_request_when_replay_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = SimpleNamespace(
        id="req-1",
        request_type=SimpleNamespace(value="decision"),
        conversation_id="conv-1",
        message_id="msg-1",
        tenant_id="tenant-1",
        project_id="project-1",
        question="Choose",
        options=[],
        context={},
        metadata={"hitl_type": "decision"},
        response="approve",
        response_metadata={},
    )

    repo = MagicMock()
    repo.mark_expired_requests = AsyncMock(return_value=0)
    repo.get_unprocessed_answered_requests = AsyncMock(return_value=[request])
    repo.get_stale_processing_requests = AsyncMock(return_value=[])
    repo.claim_for_processing = AsyncMock(return_value=request)
    repo.revert_to_answered = AsyncMock(return_value=request)

    session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = False

    continue_chat_mock = AsyncMock(
        return_value=SimpleNamespace(is_error=True, event_count=0, error_message="boom")
    )

    class _FakeAgent:
        def __init__(self, config) -> None:
            self.config = config

        async def initialize(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    monkeypatch.setattr(database_mod, "async_session_factory", lambda: session_cm)
    monkeypatch.setattr(hitl_repo_mod, "SqlHITLRequestRepository", lambda _session: repo)
    monkeypatch.setattr(execution_mod, "continue_project_chat", continue_chat_mock)
    monkeypatch.setattr(project_agent_mod, "ProjectReActAgent", _FakeAgent)
    monkeypatch.setattr(
        snapshot_repo_mod, "load_hitl_snapshot_agent_mode", AsyncMock(return_value="default")
    )

    service = HITLRecoveryService()
    recovered = await service.recover_unprocessed_requests()

    assert recovered == 0
    repo.claim_for_processing.assert_awaited_once_with("req-1", lease_owner=service._lease_owner)
    repo.revert_to_answered.assert_awaited_once_with(
        "req-1",
        lease_owner=service._lease_owner,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recovery_replays_stale_processing_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    request = SimpleNamespace(
        id="req-stale",
        request_type=SimpleNamespace(value="clarification"),
        conversation_id="conv-1",
        message_id="msg-1",
        tenant_id="tenant-1",
        project_id="project-1",
        question="Choose",
        options=[],
        context={},
        metadata={"hitl_type": "clarification"},
        status="processing",
        response="approve",
        response_metadata={},
        created_at=None,
        expires_at=None,
        answered_at=None,
    )

    repo = MagicMock()
    repo.mark_expired_requests = AsyncMock(return_value=0)
    repo.get_unprocessed_answered_requests = AsyncMock(return_value=[])
    repo.get_stale_processing_requests = AsyncMock(return_value=[request])
    repo.claim_for_processing = AsyncMock(return_value=request)
    repo.revert_to_answered = AsyncMock(return_value=request)

    session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = False

    continue_chat_mock = AsyncMock(
        return_value=SimpleNamespace(is_error=False, event_count=1, error_message=None)
    )

    class _FakeAgent:
        def __init__(self, config) -> None:
            self.config = config

        async def initialize(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    monkeypatch.setattr(database_mod, "async_session_factory", lambda: session_cm)
    monkeypatch.setattr(hitl_repo_mod, "SqlHITLRequestRepository", lambda _session: repo)
    monkeypatch.setattr(execution_mod, "continue_project_chat", continue_chat_mock)
    monkeypatch.setattr(project_agent_mod, "ProjectReActAgent", _FakeAgent)
    monkeypatch.setattr(
        snapshot_repo_mod, "load_hitl_snapshot_agent_mode", AsyncMock(return_value="default")
    )

    service = HITLRecoveryService()
    recovered = await service.recover_unprocessed_requests()

    assert recovered == 1
    repo.get_stale_processing_requests.assert_awaited_once()
    assert repo.revert_to_answered.await_count >= 1
    repo.claim_for_processing.assert_awaited_once_with(
        "req-stale",
        lease_owner=service._lease_owner,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recovery_skips_bad_payload_and_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    bad_request = SimpleNamespace(
        id="req-bad",
        request_type=SimpleNamespace(value="clarification"),
        conversation_id="conv-bad",
        message_id="msg-bad",
        tenant_id="tenant-1",
        project_id="project-1",
        question="Bad payload",
        options=[],
        context={},
        metadata={"hitl_type": "clarification"},
        response="bad",
        response_metadata={},
    )
    good_request = SimpleNamespace(
        id="req-good",
        request_type=SimpleNamespace(value="clarification"),
        conversation_id="conv-good",
        message_id="msg-good",
        tenant_id="tenant-1",
        project_id="project-1",
        question="Good payload",
        options=[],
        context={},
        metadata={"hitl_type": "clarification"},
        response="ok",
        response_metadata={},
    )

    repo = MagicMock()
    repo.mark_expired_requests = AsyncMock(return_value=0)
    repo.get_unprocessed_answered_requests = AsyncMock(return_value=[bad_request, good_request])
    repo.get_stale_processing_requests = AsyncMock(return_value=[])
    repo.claim_for_processing = AsyncMock(return_value=good_request)

    session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = False

    continue_chat_mock = AsyncMock(
        return_value=SimpleNamespace(is_error=False, event_count=1, error_message=None)
    )

    class _FakeAgent:
        def __init__(self, config) -> None:
            self.config = config

        async def initialize(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    def _restore(request: object) -> dict[str, str]:
        if getattr(request, "id", None) == "req-bad":
            raise ValueError("corrupted payload")
        return {"answer": "ok"}

    monkeypatch.setattr(database_mod, "async_session_factory", lambda: session_cm)
    monkeypatch.setattr(hitl_repo_mod, "SqlHITLRequestRepository", lambda _session: repo)
    monkeypatch.setattr(execution_mod, "continue_project_chat", continue_chat_mock)
    monkeypatch.setattr(project_agent_mod, "ProjectReActAgent", _FakeAgent)
    monkeypatch.setattr(
        snapshot_repo_mod, "load_hitl_snapshot_agent_mode", AsyncMock(return_value="default")
    )
    monkeypatch.setattr(hitl_utils, "restore_persisted_hitl_response", _restore)

    service = HITLRecoveryService()
    recovered = await service.recover_unprocessed_requests()

    assert recovered == 1
    repo.claim_for_processing.assert_awaited_once_with(
        "req-good",
        lease_owner=service._lease_owner,
    )
    continue_chat_mock.assert_awaited_once()
