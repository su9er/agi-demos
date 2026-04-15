"""Unit tests for custom runtime hook execution security boundaries."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agent.plugins.custom_hook_executor import execute_custom_hook


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_custom_hook_runs_allowlisted_script_and_audits() -> None:
    audit_service = MagicMock()
    audit_service.log_event = AsyncMock()

    with patch(
        "src.infrastructure.agent.plugins.custom_hook_executor.get_audit_service",
        return_value=audit_service,
    ):
        result = await execute_custom_hook(
            executor_kind="script",
            source_ref="src/infrastructure/agent/hooks/scripts/demo_runtime_hook.py",
            entrypoint="append_demo_response_instruction",
            hook_family="mutating",
            payload={"tenant_id": "tenant-1", "response_instructions": [], "hook_settings": {}},
        )

    assert result is not None
    assert result["demo_hook_executed"] is True
    logged_actions = [call.kwargs["action"] for call in audit_service.log_event.await_args_list]
    assert logged_actions == [
        "runtime_hook.custom_execution_started",
        "runtime_hook.custom_execution_succeeded",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_custom_hook_blocks_script_policy_family_and_audits() -> None:
    audit_service = MagicMock()
    audit_service.log_event = AsyncMock()

    with (
        patch(
            "src.infrastructure.agent.plugins.custom_hook_executor.get_audit_service",
            return_value=audit_service,
        ),
        pytest.raises(ValueError, match="not allowed"),
    ):
        await execute_custom_hook(
            executor_kind="script",
            source_ref="src/infrastructure/agent/hooks/scripts/demo_runtime_hook.py",
            entrypoint="append_demo_response_instruction",
            hook_family="policy",
            payload={"tenant_id": "tenant-1", "response_instructions": [], "hook_settings": {}},
        )

    logged_actions = [call.kwargs["action"] for call in audit_service.log_event.await_args_list]
    assert logged_actions == ["runtime_hook.custom_execution_blocked"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_custom_hook_logs_failed_audit_for_missing_entrypoint() -> None:
    audit_service = MagicMock()
    audit_service.log_event = AsyncMock()

    with (
        patch(
            "src.infrastructure.agent.plugins.custom_hook_executor.get_audit_service",
            return_value=audit_service,
        ),
        pytest.raises(ValueError, match="entrypoint is required"),
    ):
        await execute_custom_hook(
            executor_kind="script",
            source_ref="src/infrastructure/agent/hooks/scripts/demo_runtime_hook.py",
            entrypoint="",
            hook_family="mutating",
            payload={"tenant_id": "tenant-1", "response_instructions": [], "hook_settings": {}},
        )

    logged_actions = [call.kwargs["action"] for call in audit_service.log_event.await_args_list]
    assert logged_actions == ["runtime_hook.custom_execution_failed"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_custom_hook_logs_failed_audit_for_invalid_return_type() -> None:
    audit_service = MagicMock()
    audit_service.log_event = AsyncMock()

    with (
        patch(
            "src.infrastructure.agent.plugins.custom_hook_executor.get_audit_service",
            return_value=audit_service,
        ),
        pytest.raises(ValueError, match="must return dict or None"),
    ):
        await execute_custom_hook(
            executor_kind="script",
            source_ref="src/infrastructure/agent/hooks/scripts/invalid_runtime_hook.py",
            entrypoint="return_invalid_type",
            hook_family="mutating",
            payload={"tenant_id": "tenant-1", "response_instructions": [], "hook_settings": {}},
        )

    logged_actions = [call.kwargs["action"] for call in audit_service.log_event.await_args_list]
    assert logged_actions == [
        "runtime_hook.custom_execution_started",
        "runtime_hook.custom_execution_failed",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_custom_hook_logs_requires_sandbox_when_requested() -> None:
    audit_service = MagicMock()
    audit_service.log_event = AsyncMock()
    sandbox_resource = MagicMock()
    sandbox_resource.ensure_sandbox_ready = AsyncMock(return_value="sb-1")
    sandbox_resource.execute_tool = AsyncMock(
        return_value={
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"__hook_result__": {"executed_in": "sandbox"}}),
                }
            ]
        }
    )

    with (
        patch(
            "src.infrastructure.agent.plugins.custom_hook_executor.get_audit_service",
            return_value=audit_service,
        ),
        patch(
            "src.infrastructure.agent.plugins.custom_hook_executor.get_sandbox_resource_port",
            return_value=sandbox_resource,
        ),
    ):
        result = await execute_custom_hook(
            executor_kind="script",
            source_ref="src/infrastructure/agent/hooks/scripts/demo_runtime_hook.py",
            entrypoint="append_demo_response_instruction",
            hook_family="mutating",
            payload={
                "tenant_id": "tenant-1",
                "project_id": "project-1",
                "response_instructions": [],
                "hook_settings": {"isolation_mode": "sandbox"},
            },
        )

    assert result == {"executed_in": "sandbox"}
    logged_actions = [call.kwargs["action"] for call in audit_service.log_event.await_args_list]
    assert logged_actions == [
        "runtime_hook.custom_execution_started",
        "runtime_hook.custom_execution_succeeded",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_custom_hook_skips_host_import_for_sandbox_isolation() -> None:
    audit_service = MagicMock()
    audit_service.log_event = AsyncMock()
    sandbox_resource = MagicMock()
    sandbox_resource.ensure_sandbox_ready = AsyncMock(return_value="sb-1")
    sandbox_resource.execute_tool = AsyncMock(
        return_value={
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"__hook_result__": {"executed_in": "sandbox"}}),
                }
            ]
        }
    )

    with (
        patch(
            "src.infrastructure.agent.plugins.custom_hook_executor.get_audit_service",
            return_value=audit_service,
        ),
        patch(
            "src.infrastructure.agent.plugins.custom_hook_executor.get_sandbox_resource_port",
            return_value=sandbox_resource,
        ),
        patch(
            "src.infrastructure.agent.plugins.custom_hook_executor._load_module_from_path",
            side_effect=AssertionError("sandbox execution should not import on host"),
        ) as load_module,
    ):
        result = await execute_custom_hook(
            executor_kind="script",
            source_ref="src/infrastructure/agent/hooks/scripts/demo_runtime_hook.py",
            entrypoint="append_demo_response_instruction",
            hook_family="mutating",
            payload={
                "tenant_id": "tenant-1",
                "project_id": "project-1",
                "response_instructions": [],
                "hook_settings": {"isolation_mode": "sandbox"},
            },
        )

    assert result == {"executed_in": "sandbox"}
    load_module.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_custom_hook_logs_requires_sandbox_when_context_missing() -> None:
    audit_service = MagicMock()
    audit_service.log_event = AsyncMock()

    with (
        patch(
            "src.infrastructure.agent.plugins.custom_hook_executor.get_audit_service",
            return_value=audit_service,
        ),
        pytest.raises(RuntimeError, match="requires project_id and tenant_id"),
    ):
        await execute_custom_hook(
            executor_kind="script",
            source_ref="src/infrastructure/agent/hooks/scripts/demo_runtime_hook.py",
            entrypoint="append_demo_response_instruction",
            hook_family="mutating",
            payload={
                "tenant_id": "tenant-1",
                "response_instructions": [],
                "hook_settings": {"isolation_mode": "sandbox"},
            },
        )

    logged_actions = [call.kwargs["action"] for call in audit_service.log_event.await_args_list]
    assert logged_actions == ["runtime_hook.custom_execution_requires_sandbox"]
