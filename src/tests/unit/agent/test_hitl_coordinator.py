"""Unit tests for HITLCoordinator response validation."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.domain.model.agent.hitl_types import HITLType
from src.infrastructure.agent.hitl import coordinator as coordinator_mod
from src.infrastructure.agent.hitl.coordinator import ResolveResult


@pytest.fixture(autouse=True)
def _stub_mark_hitl_completed(monkeypatch) -> AsyncMock:
    completion_mock = AsyncMock()
    monkeypatch.setattr(coordinator_mod, "mark_hitl_request_completed", completion_mock)
    return completion_mock


@pytest.fixture(autouse=True)
def _stub_mark_hitl_timeout(monkeypatch) -> AsyncMock:
    timeout_mock = AsyncMock()
    monkeypatch.setattr(coordinator_mod, "mark_hitl_request_timeout", timeout_mock)
    return timeout_mock


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_by_request_id_rejects_mismatched_scope(monkeypatch) -> None:
    monkeypatch.setattr(coordinator_mod, "_persist_hitl_request", AsyncMock())
    coordinator = coordinator_mod.HITLCoordinator(
        conversation_id="conv-1",
        tenant_id="tenant-1",
        project_id="project-1",
        message_id="msg-1",
    )
    request_id = await coordinator.prepare_request(
        HITLType.ENV_VAR,
        request_data={
            "tool_name": "web_search",
            "fields": [{"name": "API_KEY", "label": "API Key"}],
        },
    )

    resolved = coordinator_mod.resolve_by_request_id(
        request_id,
        {"values": {"API_KEY": "secret"}},
        tenant_id="tenant-2",
        project_id="project-1",
        conversation_id="conv-1",
        message_id="msg-1",
    )

    assert resolved is ResolveResult.REJECTED
    assert coordinator.pending_count == 1

    resolved = coordinator_mod.resolve_by_request_id(
        request_id,
        {"values": {"API_KEY": "secret"}},
        tenant_id="tenant-1",
        project_id="project-1",
        conversation_id="conv-1",
        message_id="msg-1",
    )

    assert resolved is ResolveResult.RESOLVED
    result = await coordinator.wait_for_response(request_id, HITLType.ENV_VAR, timeout_seconds=0.1)
    assert result == {"values": {"API_KEY": "secret"}}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_by_request_id_rejects_invalid_env_var_semantics(monkeypatch) -> None:
    monkeypatch.setattr(coordinator_mod, "_persist_hitl_request", AsyncMock())
    coordinator = coordinator_mod.HITLCoordinator(
        conversation_id="conv-1",
        tenant_id="tenant-1",
        project_id="project-1",
        message_id="msg-1",
    )
    request_id = await coordinator.prepare_request(
        HITLType.ENV_VAR,
        request_data={
            "tool_name": "web_search",
            "fields": [{"name": "API_KEY", "label": "API Key", "required": True}],
        },
    )

    resolved = coordinator_mod.resolve_by_request_id(
        request_id,
        {"values": {"OTHER_KEY": "secret"}},
        tenant_id="tenant-1",
        project_id="project-1",
        conversation_id="conv-1",
        message_id="msg-1",
    )

    assert resolved is ResolveResult.REJECTED
    assert coordinator.pending_count == 1

    resolved = coordinator_mod.resolve_by_request_id(
        request_id,
        {"values": {"API_KEY": "secret"}},
        tenant_id="tenant-1",
        project_id="project-1",
        conversation_id="conv-1",
        message_id="msg-1",
    )

    assert resolved is ResolveResult.RESOLVED
    result = await coordinator.wait_for_response(request_id, HITLType.ENV_VAR, timeout_seconds=0.1)
    assert result == {"values": {"API_KEY": "secret"}}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_by_request_id_rejects_invalid_a2ui_action_semantics(monkeypatch) -> None:
    monkeypatch.setattr(coordinator_mod, "_persist_hitl_request", AsyncMock())
    coordinator = coordinator_mod.HITLCoordinator(
        conversation_id="conv-a2ui",
        tenant_id="tenant-1",
        project_id="project-1",
        message_id="msg-a2ui",
    )
    request_id = await coordinator.prepare_request(
        HITLType.A2UI_ACTION,
        request_data={
            "title": "Review",
            "block_id": "block-1",
            "allowed_actions": [
                {
                    "source_component_id": "button-1",
                    "action_name": "submit",
                }
            ],
        },
    )

    resolved = coordinator_mod.resolve_by_request_id(
        request_id,
        {
            "action_name": "approve",
            "source_component_id": "button-1",
            "context": {},
        },
        tenant_id="tenant-1",
        project_id="project-1",
        conversation_id="conv-a2ui",
        message_id="msg-a2ui",
    )

    assert resolved is ResolveResult.REJECTED
    assert coordinator.pending_count == 1

    resolved = coordinator_mod.resolve_by_request_id(
        request_id,
        {
            "action_name": "submit",
            "source_component_id": "button-1",
            "context": {},
        },
        tenant_id="tenant-1",
        project_id="project-1",
        conversation_id="conv-a2ui",
        message_id="msg-a2ui",
    )

    assert resolved is ResolveResult.RESOLVED
    result = await coordinator.wait_for_response(
        request_id,
        HITLType.A2UI_ACTION,
        timeout_seconds=0.1,
    )
    assert result == {
        "action_name": "submit",
        "source_component_id": "button-1",
        "context": {},
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_by_request_id_rejects_optional_non_string_env_var_value(monkeypatch) -> None:
    monkeypatch.setattr(coordinator_mod, "_persist_hitl_request", AsyncMock())
    coordinator = coordinator_mod.HITLCoordinator(
        conversation_id="conv-opt",
        tenant_id="tenant-1",
        project_id="project-1",
        message_id="msg-opt",
    )
    request_id = await coordinator.prepare_request(
        HITLType.ENV_VAR,
        request_data={
            "tool_name": "web_search",
            "fields": [{"name": "OPTIONAL_TOKEN", "label": "Optional token", "required": False}],
        },
    )

    resolved = coordinator_mod.resolve_by_request_id(
        request_id,
        {"values": {"OPTIONAL_TOKEN": 123}},
        tenant_id="tenant-1",
        project_id="project-1",
        conversation_id="conv-opt",
        message_id="msg-opt",
    )

    assert resolved is ResolveResult.REJECTED
    assert coordinator.pending_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_by_request_id_accepts_bare_env_var_mapping(monkeypatch) -> None:
    monkeypatch.setattr(coordinator_mod, "_persist_hitl_request", AsyncMock())
    coordinator = coordinator_mod.HITLCoordinator(
        conversation_id="conv-bare",
        tenant_id="tenant-1",
        project_id="project-1",
        message_id="msg-bare",
    )
    request_id = await coordinator.prepare_request(
        HITLType.ENV_VAR,
        request_data={
            "tool_name": "web_search",
            "fields": [{"name": "API_KEY", "label": "API Key", "required": True}],
        },
    )

    resolved = coordinator_mod.resolve_by_request_id(
        request_id,
        {"API_KEY": "secret"},
        tenant_id="tenant-1",
        project_id="project-1",
        conversation_id="conv-bare",
        message_id="msg-bare",
    )

    assert resolved is ResolveResult.RESOLVED
    result = await coordinator.wait_for_response(request_id, HITLType.ENV_VAR, timeout_seconds=0.1)
    assert result == {"values": {"API_KEY": "secret"}}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_response_raises_timeout(monkeypatch) -> None:
    monkeypatch.setattr(coordinator_mod, "_persist_hitl_request", AsyncMock())
    coordinator = coordinator_mod.HITLCoordinator(
        conversation_id="conv-timeout",
        tenant_id="tenant-1",
        project_id="project-1",
        message_id="msg-timeout",
        default_timeout=0.01,
    )
    request_id = await coordinator.prepare_request(
        HITLType.ENV_VAR,
        request_data={
            "tool_name": "web_search",
            "fields": [{"name": "API_KEY", "label": "API Key"}],
        },
        timeout_seconds=0.01,
    )

    with pytest.raises(TimeoutError):
        await coordinator.wait_for_response(request_id, HITLType.ENV_VAR, timeout_seconds=0.01)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_response_marks_request_timeout(
    monkeypatch,
    _stub_mark_hitl_timeout: AsyncMock,
) -> None:
    monkeypatch.setattr(coordinator_mod, "_persist_hitl_request", AsyncMock())
    coordinator = coordinator_mod.HITLCoordinator(
        conversation_id="conv-timeout-mark",
        tenant_id="tenant-1",
        project_id="project-1",
        message_id="msg-timeout-mark",
        default_timeout=0.01,
    )
    request_id = await coordinator.prepare_request(
        HITLType.CLARIFICATION,
        request_data={"question": "Need input", "allow_custom": True},
        timeout_seconds=0.01,
    )

    with pytest.raises(TimeoutError):
        await coordinator.wait_for_response(
            request_id,
            HITLType.CLARIFICATION,
            timeout_seconds=0.01,
        )

    _stub_mark_hitl_timeout.assert_awaited_once_with(request_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_response_requires_explicit_completion(
    monkeypatch,
    _stub_mark_hitl_completed: AsyncMock,
) -> None:
    monkeypatch.setattr(coordinator_mod, "_persist_hitl_request", AsyncMock())
    coordinator = coordinator_mod.HITLCoordinator(
        conversation_id="conv-done",
        tenant_id="tenant-1",
        project_id="project-1",
        message_id="msg-done",
    )
    request_id = await coordinator.prepare_request(
        HITLType.CLARIFICATION,
        request_data={"question": "Choose", "allow_custom": True},
    )

    resolved = coordinator_mod.resolve_by_request_id(
        request_id,
        {"answer": "ok"},
        tenant_id="tenant-1",
        project_id="project-1",
        conversation_id="conv-done",
        message_id="msg-done",
    )

    assert resolved is ResolveResult.RESOLVED
    assert (
        await coordinator.wait_for_response(request_id, HITLType.CLARIFICATION, timeout_seconds=0.1)
        == "ok"
    )
    _stub_mark_hitl_completed.assert_not_awaited()

    await coordinator.complete_request(request_id)
    _stub_mark_hitl_completed.assert_awaited_once_with(request_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_completion_unblocks_after_explicit_complete(
    monkeypatch,
    _stub_mark_hitl_completed: AsyncMock,
) -> None:
    monkeypatch.setattr(coordinator_mod, "_persist_hitl_request", AsyncMock())
    coordinator = coordinator_mod.HITLCoordinator(
        conversation_id="conv-complete",
        tenant_id="tenant-1",
        project_id="project-1",
        message_id="msg-complete",
    )
    request_id = await coordinator.prepare_request(
        HITLType.CLARIFICATION,
        request_data={"question": "Choose", "allow_custom": True},
    )

    wait_task = asyncio.create_task(
        coordinator_mod.wait_for_request_completion(request_id, timeout_seconds=0.5)
    )
    await asyncio.sleep(0)
    assert wait_task.done() is False

    resolved = coordinator_mod.resolve_by_request_id(
        request_id,
        {"answer": "ok"},
        tenant_id="tenant-1",
        project_id="project-1",
        conversation_id="conv-complete",
        message_id="msg-complete",
    )

    assert resolved is ResolveResult.RESOLVED
    assert (
        await coordinator.wait_for_response(request_id, HITLType.CLARIFICATION, timeout_seconds=0.1)
        == "ok"
    )
    assert wait_task.done() is False

    await coordinator_mod.complete_hitl_request(request_id)
    await wait_task
    _stub_mark_hitl_completed.assert_awaited_once_with(request_id)


@pytest.mark.unit
def test_validate_hitl_response_rejects_invalid_a2ui_payload() -> None:
    is_valid, error = coordinator_mod.validate_hitl_response(
        hitl_type=HITLType.A2UI_ACTION,
        request_data={
            "_request_id": "req-a2ui",
            "title": "Pick an action",
            "context": {},
        },
        response_data={
            "action_name": "",
            "source_component_id": "toolbar",
            "context": {},
        },
        conversation_id="conv-1",
        tenant_id="tenant-1",
        project_id="project-1",
        message_id="msg-1",
        received_tenant_id="tenant-1",
        received_project_id="project-1",
        received_conversation_id="conv-1",
        received_message_id="msg-1",
    )

    assert is_valid is False
    assert error == "Rejected invalid HITL response semantics"
