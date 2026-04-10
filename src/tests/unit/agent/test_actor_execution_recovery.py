"""Unit tests for Actor execution HITL recovery."""

from unittest.mock import AsyncMock

import pytest

from src.infrastructure.agent.actor import execution
from src.infrastructure.agent.hitl import coordinator as hitl_coordinator_mod
from src.infrastructure.agent.hitl.state_store import HITLAgentState


class _FakeAgent:
    def __init__(self) -> None:
        self.calls = []

    async def execute_chat(
        self,
        conversation_id,
        user_message,
        user_id,
        conversation_context,
        tenant_id,
        message_id,
        hitl_response=None,
    ):
        self.calls.append(
            {
                "conversation_id": conversation_id,
                "user_message": user_message,
                "user_id": user_id,
                "conversation_context": conversation_context,
                "tenant_id": tenant_id,
                "message_id": message_id,
                "hitl_response": hitl_response,
            }
        )
        yield {"type": "complete", "data": {"content": "ok"}}


class _FakeStateStore:
    def __init__(self, redis_client) -> None:
        self.deleted_request_id = None

    async def load_state_by_request(self, request_id):
        return None

    async def delete_state_by_request(self, request_id):
        self.deleted_request_id = request_id
        return True


class _SummaryFakeAgent(_FakeAgent):
    async def execute_chat(
        self,
        conversation_id,
        user_message,
        user_id,
        conversation_context,
        tenant_id,
        message_id,
        hitl_response=None,
    ):
        self.calls.append(
            {
                "conversation_id": conversation_id,
                "user_message": user_message,
                "user_id": user_id,
                "conversation_context": conversation_context,
                "tenant_id": tenant_id,
                "message_id": message_id,
                "hitl_response": hitl_response,
            }
        )
        yield {"type": "context_summary_generated", "data": {"summary": "saved"}}
        yield {"type": "complete", "data": {"content": "ok"}}


class _ErrorAgent(_FakeAgent):
    async def execute_chat(
        self,
        conversation_id,
        user_message,
        user_id,
        conversation_context,
        tenant_id,
        message_id,
        hitl_response=None,
    ):
        self.calls.append(
            {
                "conversation_id": conversation_id,
                "user_message": user_message,
                "user_id": user_id,
                "conversation_context": conversation_context,
                "tenant_id": tenant_id,
                "message_id": message_id,
                "hitl_response": hitl_response,
            }
        )
        if False:
            yield {"type": "noop", "data": {}}
        raise RuntimeError("resume failed")


@pytest.fixture(autouse=True)
def _stub_mark_hitl_completed(monkeypatch) -> AsyncMock:
    completion_mock = AsyncMock()
    monkeypatch.setattr(hitl_coordinator_mod, "mark_hitl_request_completed", completion_mock)
    return completion_mock


@pytest.mark.unit
class TestActorExecutionRecovery:
    """Tests HITL resume path with snapshot fallback."""

    async def test_continue_chat_recovers_from_snapshot(
        self, monkeypatch, _stub_mark_hitl_completed: AsyncMock
    ):
        state = HITLAgentState(
            conversation_id="conv-1",
            message_id="msg-1",
            tenant_id="tenant-1",
            project_id="project-1",
            hitl_request_id="req-1",
            hitl_type="clarification",
            hitl_request_data={"question": "q"},
            messages=[{"role": "user", "content": "hi"}],
            user_message="hi",
            user_id="user-1",
            correlation_id="corr-1",
            timeout_seconds=120.0,
        )

        agent = _FakeAgent()

        monkeypatch.setattr(execution, "_get_redis_client", AsyncMock(return_value=object()))
        monkeypatch.setattr(execution, "_publish_event_to_stream", AsyncMock())
        monkeypatch.setattr(execution, "_persist_events", AsyncMock())
        monkeypatch.setattr(execution, "set_agent_running", AsyncMock())
        monkeypatch.setattr(execution, "refresh_agent_running_ttl", AsyncMock())
        monkeypatch.setattr(execution, "clear_agent_running", AsyncMock())
        monkeypatch.setattr(execution, "delete_hitl_snapshot", AsyncMock())
        monkeypatch.setattr(execution, "load_hitl_snapshot", AsyncMock(return_value=state))
        monkeypatch.setattr(execution, "HITLStateStore", _FakeStateStore)

        result = await execution.continue_project_chat(
            agent,
            "req-1",
            {"answer": "ok"},
            tenant_id="tenant-1",
            project_id="project-1",
            conversation_id="conv-1",
            message_id="msg-1",
        )

        assert result.is_error is False
        assert result.content == "ok"
        assert agent.calls
        assert agent.calls[0]["conversation_context"] == state.messages
        execution.load_hitl_snapshot.assert_awaited_once_with("req-1")
        _stub_mark_hitl_completed.assert_awaited_once_with("req-1", lease_owner=None)

    async def test_continue_chat_keeps_recovery_state_when_completion_is_rejected(
        self, monkeypatch, _stub_mark_hitl_completed: AsyncMock
    ):
        state = HITLAgentState(
            conversation_id="conv-1",
            message_id="msg-1",
            tenant_id="tenant-1",
            project_id="project-1",
            hitl_request_id="req-1",
            hitl_type="clarification",
            hitl_request_data={"question": "q"},
            messages=[{"role": "user", "content": "hi"}],
            user_message="hi",
            user_id="user-1",
            correlation_id="corr-1",
            timeout_seconds=120.0,
        )

        agent = _FakeAgent()
        fake_state_store = _FakeStateStore(redis_client=object())
        delete_snapshot = AsyncMock()
        _stub_mark_hitl_completed.return_value = False

        monkeypatch.setattr(execution, "_get_redis_client", AsyncMock(return_value=object()))
        monkeypatch.setattr(execution, "_publish_event_to_stream", AsyncMock())
        monkeypatch.setattr(execution, "_persist_events", AsyncMock())
        monkeypatch.setattr(execution, "set_agent_running", AsyncMock())
        monkeypatch.setattr(execution, "refresh_agent_running_ttl", AsyncMock())
        monkeypatch.setattr(execution, "clear_agent_running", AsyncMock())
        monkeypatch.setattr(execution, "delete_hitl_snapshot", delete_snapshot)
        monkeypatch.setattr(execution, "load_hitl_snapshot", AsyncMock(return_value=state))
        monkeypatch.setattr(execution, "HITLStateStore", lambda _redis: fake_state_store)

        result = await execution.continue_project_chat(
            agent,
            "req-1",
            {"answer": "ok"},
            lease_owner="worker-1",
            tenant_id="tenant-1",
            project_id="project-1",
            conversation_id="conv-1",
            message_id="msg-1",
        )

        assert result.is_error is False
        assert fake_state_store.deleted_request_id is None
        delete_snapshot.assert_not_awaited()
        _stub_mark_hitl_completed.assert_awaited_once_with("req-1", lease_owner="worker-1")

    async def test_continue_chat_persists_context_summary_side_effects(self, monkeypatch):
        state = HITLAgentState(
            conversation_id="conv-1",
            message_id="msg-1",
            tenant_id="tenant-1",
            project_id="project-1",
            hitl_request_id="req-1",
            hitl_type="clarification",
            hitl_request_data={"question": "q"},
            messages=[{"role": "user", "content": "hi"}],
            user_message="hi",
            user_id="user-1",
            correlation_id="corr-1",
            timeout_seconds=120.0,
        )

        agent = _SummaryFakeAgent()

        monkeypatch.setattr(execution, "_get_redis_client", AsyncMock(return_value=object()))
        monkeypatch.setattr(execution, "_publish_event_to_stream", AsyncMock())
        monkeypatch.setattr(execution, "_persist_events", AsyncMock())
        monkeypatch.setattr(execution, "_flush_remaining_events", AsyncMock())
        monkeypatch.setattr(execution, "_save_context_summary", AsyncMock())
        monkeypatch.setattr(execution, "set_agent_running", AsyncMock())
        monkeypatch.setattr(execution, "refresh_agent_running_ttl", AsyncMock())
        monkeypatch.setattr(execution, "clear_agent_running", AsyncMock())
        monkeypatch.setattr(execution, "delete_hitl_snapshot", AsyncMock())
        monkeypatch.setattr(execution, "load_hitl_snapshot", AsyncMock(return_value=state))
        monkeypatch.setattr(execution, "HITLStateStore", _FakeStateStore)

        result = await execution.continue_project_chat(
            agent,
            "req-1",
            {"answer": "ok"},
            tenant_id="tenant-1",
            project_id="project-1",
            conversation_id="conv-1",
            message_id="msg-1",
        )

        assert result.is_error is False
        execution._save_context_summary.assert_awaited_once_with(
            conversation_id="conv-1",
            summary_data={"summary": "saved"},
            last_event_time_us=result.last_event_time_us,
        )

    async def test_continue_chat_rejects_binding_mismatch(self, monkeypatch):
        state = HITLAgentState(
            conversation_id="conv-1",
            message_id="msg-1",
            tenant_id="tenant-1",
            project_id="project-1",
            hitl_request_id="req-1",
            hitl_type="clarification",
            hitl_request_data={"question": "q", "allow_custom": True},
            messages=[{"role": "user", "content": "hi"}],
            user_message="hi",
            user_id="user-1",
            correlation_id="corr-1",
            timeout_seconds=120.0,
        )

        agent = _FakeAgent()

        monkeypatch.setattr(execution, "_get_redis_client", AsyncMock(return_value=object()))
        monkeypatch.setattr(execution, "_publish_event_to_stream", AsyncMock())
        monkeypatch.setattr(execution, "_persist_events", AsyncMock())
        monkeypatch.setattr(execution, "set_agent_running", AsyncMock())
        monkeypatch.setattr(execution, "refresh_agent_running_ttl", AsyncMock())
        monkeypatch.setattr(execution, "clear_agent_running", AsyncMock())
        monkeypatch.setattr(execution, "delete_hitl_snapshot", AsyncMock())
        monkeypatch.setattr(execution, "load_hitl_snapshot", AsyncMock(return_value=state))
        monkeypatch.setattr(execution, "HITLStateStore", _FakeStateStore)

        result = await execution.continue_project_chat(
            agent,
            "req-1",
            {"answer": "ok"},
            tenant_id="tenant-1",
            project_id="project-1",
            conversation_id="conv-2",
            message_id="msg-1",
        )

        assert result.is_error is True
        assert result.error_message == "Rejected HITL response due to binding mismatch"
        assert not agent.calls
        execution.delete_hitl_snapshot.assert_not_awaited()

    async def test_continue_chat_keeps_recovery_state_on_resume_error(
        self, monkeypatch, _stub_mark_hitl_completed: AsyncMock
    ):
        state = HITLAgentState(
            conversation_id="conv-1",
            message_id="msg-1",
            tenant_id="tenant-1",
            project_id="project-1",
            hitl_request_id="req-1",
            hitl_type="clarification",
            hitl_request_data={"question": "q"},
            messages=[{"role": "user", "content": "hi"}],
            user_message="hi",
            user_id="user-1",
            correlation_id="corr-1",
            timeout_seconds=120.0,
        )

        agent = _ErrorAgent()

        monkeypatch.setattr(execution, "_get_redis_client", AsyncMock(return_value=object()))
        monkeypatch.setattr(execution, "_publish_event_to_stream", AsyncMock())
        monkeypatch.setattr(execution, "_persist_events", AsyncMock())
        monkeypatch.setattr(execution, "set_agent_running", AsyncMock())
        monkeypatch.setattr(execution, "refresh_agent_running_ttl", AsyncMock())
        monkeypatch.setattr(execution, "clear_agent_running", AsyncMock())
        monkeypatch.setattr(execution, "delete_hitl_snapshot", AsyncMock())
        monkeypatch.setattr(execution, "load_hitl_snapshot", AsyncMock(return_value=state))
        monkeypatch.setattr(execution, "HITLStateStore", _FakeStateStore)

        result = await execution.continue_project_chat(
            agent,
            "req-1",
            {"answer": "ok"},
            tenant_id="tenant-1",
            project_id="project-1",
            conversation_id="conv-1",
            message_id="msg-1",
        )

        assert result.is_error is True
        _stub_mark_hitl_completed.assert_not_awaited()
        execution.delete_hitl_snapshot.assert_not_awaited()
