"""Unit tests for RayHITLHandler."""

from unittest.mock import AsyncMock

import pytest

from src.domain.model.agent.hitl_types import HITLPendingException, HITLType
from src.infrastructure.agent.hitl import ray_hitl_handler
from src.infrastructure.agent.hitl.ray_hitl_handler import RayHITLHandler
from src.infrastructure.agent.hitl.utils import build_stable_hitl_request_id


@pytest.mark.unit
class TestRayHITLHandler:
    """Tests for RayHITLHandler."""

    async def test_request_clarification_persists_and_raises(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-1",
            tenant_id="tenant-1",
            project_id="project-1",
            message_id="msg-1",
            default_timeout=120.0,
        )

        with pytest.raises(HITLPendingException) as exc_info:
            await handler.request_clarification(
                question="Need clarification?",
                options=["yes", "no"],
                request_id="clar_123",
            )

        assert exc_info.value.request_id == "clar_123"
        assert exc_info.value.hitl_type == HITLType.CLARIFICATION

        persist_mock.assert_awaited_once()
        emit_mock.assert_awaited_once()
        assert persist_mock.call_args.kwargs["request_id"] == "clar_123"
        assert persist_mock.call_args.kwargs["hitl_type"] == HITLType.CLARIFICATION

    async def test_preinjected_response_short_circuits(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-2",
            tenant_id="tenant-2",
            project_id="project-2",
            message_id="msg-2",
            preinjected_response={
                "request_id": "deci_123",
                "hitl_type": "decision",
                "conversation_id": "conv-2",
                "tenant_id": "tenant-2",
                "project_id": "project-2",
                "message_id": "msg-2",
                "response_data": {"decision": "approve"},
            },
        )

        result = await handler.request_decision(
            question="Approve?",
            options=["approve", "deny"],
            request_id="deci_123",
        )

        assert result == "approve"
        persist_mock.assert_not_called()
        emit_mock.assert_not_called()

    async def test_preinjected_response_missing_scope_fields_falls_back_to_hitl(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-2b",
            tenant_id="tenant-2b",
            project_id="project-2b",
            message_id="msg-2b",
            preinjected_response={
                "request_id": "clar_456",
                "hitl_type": "clarification",
                "response_data": {"answer": "approve"},
            },
        )

        with pytest.raises(HITLPendingException):
            await handler.request_clarification(
                question="Approve?",
                options=[],
                request_id="clar_456",
            )

        persist_mock.assert_awaited_once()
        emit_mock.assert_awaited_once()

    async def test_preinjected_malformed_response_data_falls_back_to_hitl(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-2c",
            tenant_id="tenant-2c",
            project_id="project-2c",
            message_id="msg-2c",
            preinjected_response={
                "request_id": "clar_789",
                "hitl_type": "clarification",
                "conversation_id": "conv-2c",
                "tenant_id": "tenant-2c",
                "project_id": "project-2c",
                "message_id": "msg-2c",
                "response_data": "{not-json}",
            },
        )

        with pytest.raises(HITLPendingException):
            await handler.request_clarification(
                question="Need input?",
                options=[],
                request_id="clar_789",
            )

        assert handler._preinjected_response is None
        persist_mock.assert_awaited_once()
        emit_mock.assert_awaited_once()

    async def test_preinjected_response_without_request_id_fails_closed(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-3",
            tenant_id="tenant-3",
            project_id="project-3",
            preinjected_response={
                "hitl_type": "permission",
                "response_data": {"granted": True},
            },
        )

        with pytest.raises(HITLPendingException):
            await handler.request_permission(
                tool_name="bash",
                action="run command",
            )

        persist_mock.assert_awaited_once()
        emit_mock.assert_awaited_once()

    async def test_preinjected_clarification_list_response_short_circuits(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-3a",
            tenant_id="tenant-3a",
            project_id="project-3a",
            message_id="msg-3a",
            preinjected_response={
                "request_id": "clar-list",
                "hitl_type": "clarification",
                "conversation_id": "conv-3a",
                "tenant_id": "tenant-3a",
                "project_id": "project-3a",
                "message_id": "msg-3a",
                "response_data": {"answer": ["opt-1", "opt-2"]},
            },
        )

        result = await handler.request_clarification(
            question="Choose options",
            options=[{"id": "opt-1", "label": "One"}, {"id": "opt-2", "label": "Two"}],
            allow_custom=False,
            request_id="clar-list",
        )

        assert result == ["opt-1", "opt-2"]
        persist_mock.assert_not_called()
        emit_mock.assert_not_called()

    async def test_preinjected_decision_exceeding_max_selections_falls_back_to_hitl(
        self,
        monkeypatch,
    ):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-3b",
            tenant_id="tenant-3b",
            project_id="project-3b",
            message_id="msg-3b",
            preinjected_response={
                "request_id": "deci-max",
                "hitl_type": "decision",
                "conversation_id": "conv-3b",
                "tenant_id": "tenant-3b",
                "project_id": "project-3b",
                "message_id": "msg-3b",
                "response_data": {"decision": ["a", "b"]},
            },
        )

        with pytest.raises(HITLPendingException):
            await handler.request_decision(
                question="Pick one",
                options=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                max_selections=1,
                request_id="deci-max",
            )

        persist_mock.assert_awaited_once()
        emit_mock.assert_awaited_once()

    async def test_preinjected_clarification_allows_mixed_custom_multi_select(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-3custom",
            tenant_id="tenant-3custom",
            project_id="project-3custom",
            message_id="msg-3custom",
            preinjected_response={
                "request_id": "clar-custom-list",
                "hitl_type": "clarification",
                "conversation_id": "conv-3custom",
                "tenant_id": "tenant-3custom",
                "project_id": "project-3custom",
                "message_id": "msg-3custom",
                "response_data": {"answer": ["opt-1", "custom note"]},
            },
        )

        result = await handler.request_clarification(
            question="Choose options",
            options=[{"id": "opt-1", "label": "One"}, {"id": "opt-2", "label": "Two"}],
            allow_custom=True,
            request_id="clar-custom-list",
        )

        assert result == ["opt-1", "custom note"]
        persist_mock.assert_not_called()
        emit_mock.assert_not_called()

    async def test_preinjected_single_choice_decision_list_falls_back_to_hitl(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-3c",
            tenant_id="tenant-3c",
            project_id="project-3c",
            message_id="msg-3c",
            preinjected_response={
                "request_id": "deci-single-list",
                "hitl_type": "decision",
                "conversation_id": "conv-3c",
                "tenant_id": "tenant-3c",
                "project_id": "project-3c",
                "message_id": "msg-3c",
                "response_data": {"decision": ["a", "b"]},
            },
        )

        with pytest.raises(HITLPendingException):
            await handler.request_decision(
                question="Pick one",
                options=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                selection_mode="single",
                request_id="deci-single-list",
            )

        persist_mock.assert_awaited_once()
        emit_mock.assert_awaited_once()

    async def test_preinjected_env_var_missing_required_value_falls_back_to_hitl(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-3d",
            tenant_id="tenant-3d",
            project_id="project-3d",
            message_id="msg-3d",
            preinjected_response={
                "request_id": "env-missing-required",
                "hitl_type": "env_var",
                "conversation_id": "conv-3d",
                "tenant_id": "tenant-3d",
                "project_id": "project-3d",
                "message_id": "msg-3d",
                "response_data": {"values": {}},
            },
        )

        with pytest.raises(HITLPendingException):
            await handler.request_env_vars(
                tool_name="web_search",
                fields=[{"name": "API_KEY", "label": "API_KEY", "required": True}],
                request_id="env-missing-required",
            )

        persist_mock.assert_awaited_once()
        emit_mock.assert_awaited_once()

    async def test_preinjected_env_var_allows_blank_optional_values(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-3e",
            tenant_id="tenant-3e",
            project_id="project-3e",
            message_id="msg-3e",
            preinjected_response={
                "request_id": "env-blank-optional",
                "hitl_type": "env_var",
                "conversation_id": "conv-3e",
                "tenant_id": "tenant-3e",
                "project_id": "project-3e",
                "message_id": "msg-3e",
                "response_data": {"values": {"API_KEY": " secret ", "OPTIONAL": "   "}},
            },
        )

        result = await handler.request_env_vars(
            tool_name="web_search",
            fields=[
                {"name": "API_KEY", "label": "API_KEY", "required": True},
                {"name": "OPTIONAL", "label": "OPTIONAL", "required": False},
            ],
            request_id="env-blank-optional",
        )

        assert result == {"API_KEY": " secret ", "OPTIONAL": "   "}
        persist_mock.assert_not_called()
        emit_mock.assert_not_called()

    async def test_preinjected_permission_response_short_circuits(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        payload = {
            "tool_name": "bash",
            "action": "run command",
            "risk_level": "medium",
            "description": "Run safe command",
            "details": {},
            "allow_remember": True,
        }
        request_id = build_stable_hitl_request_id(
            "perm",
            tenant_id="tenant-4",
            project_id="project-4",
            conversation_id="conv-4",
            message_id="msg-4",
            call_id=None,
            payload=payload,
        )

        handler = RayHITLHandler(
            conversation_id="conv-4",
            tenant_id="tenant-4",
            project_id="project-4",
            message_id="msg-4",
            preinjected_response={
                "request_id": request_id,
                "hitl_type": "permission",
                "conversation_id": "conv-4",
                "tenant_id": "tenant-4",
                "project_id": "project-4",
                "message_id": "msg-4",
                "response_data": {"action": "allow"},
            },
        )

        granted = await handler.request_permission(
            tool_name="bash",
            action="run command",
            description="Run safe command",
            request_id=request_id,
        )

        assert granted is True
        persist_mock.assert_not_called()
        emit_mock.assert_not_called()

    async def test_preinjected_permission_conflict_falls_back_to_hitl(self, monkeypatch):
        persist_mock = AsyncMock()
        emit_mock = AsyncMock()

        monkeypatch.setattr(ray_hitl_handler, "_persist_hitl_request", persist_mock)
        monkeypatch.setattr(ray_hitl_handler, "_emit_hitl_sse_event", emit_mock)

        handler = RayHITLHandler(
            conversation_id="conv-4b",
            tenant_id="tenant-4b",
            project_id="project-4b",
            message_id="msg-4b",
            preinjected_response={
                "request_id": "perm-conflict",
                "hitl_type": "permission",
                "conversation_id": "conv-4b",
                "tenant_id": "tenant-4b",
                "project_id": "project-4b",
                "message_id": "msg-4b",
                "response_data": {"action": "deny", "granted": True},
            },
        )

        with pytest.raises(HITLPendingException):
            await handler.request_permission(
                tool_name="bash",
                action="run command",
                description="Run safe command",
                request_id="perm-conflict",
            )

        persist_mock.assert_awaited_once()
        emit_mock.assert_awaited_once()
