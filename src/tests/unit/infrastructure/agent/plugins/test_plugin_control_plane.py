"""Unit tests for plugin control-plane service."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.agent.plugins.control_plane import PluginControlPlaneService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_runtime_plugins_enriches_channel_types() -> None:
    """Runtime list should include channel_types grouped by plugin ownership."""
    runtime_manager = SimpleNamespace(
        ensure_loaded=AsyncMock(return_value=[]),
        list_plugins=lambda **_kwargs: (
            [
                {
                    "name": "plugin-a",
                    "enabled": True,
                    "discovered": True,
                }
            ],
            [],
        ),
    )
    registry = SimpleNamespace(
        list_channel_adapter_factories=lambda: {"feishu": ("plugin-a", object())},
        list_channel_type_metadata=dict,
        list_tool_factories=dict,
        list_hooks=dict,
        list_commands=dict,
        list_services=dict,
        list_providers=dict,
    )
    service = PluginControlPlaneService(runtime_manager=runtime_manager, registry=registry)

    records, diagnostics, channel_types_by_plugin = await service.list_runtime_plugins()

    assert diagnostics == []
    assert records[0]["channel_types"] == ["feishu"]
    assert channel_types_by_plugin == {"plugin-a": ["feishu"]}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_plugin_enabled_attaches_reload_plan_and_control_trace() -> None:
    """Enable/disable actions should include reconcile plan and control-plane trace."""
    runtime_manager = SimpleNamespace(
        set_plugin_enabled=AsyncMock(return_value=[]),
        is_plugin_enabled=lambda plugin_name, tenant_id=None: (
            plugin_name == "plugin-a" and tenant_id == "tenant-1"
        ),
    )
    registry = SimpleNamespace(
        list_channel_type_metadata=lambda: {"feishu": object()},
        list_tool_factories=lambda: {"plugin-a": object()},
        list_hooks=lambda: {"before_tool_selection": {"plugin-a": object()}},
        list_commands=lambda: {"echo": ("plugin-a", object())},
        list_services=lambda: {"skill-index": ("plugin-a", object())},
        list_providers=lambda: {"embedding": ("plugin-a", object())},
    )
    service = PluginControlPlaneService(
        runtime_manager=runtime_manager,
        registry=registry,
        reconcile_channel_runtime=AsyncMock(return_value={"restart": 1}),
    )

    result = await service.set_plugin_enabled(
        "plugin-a",
        enabled=True,
        tenant_id="tenant-1",
    )

    assert result.success is True
    assert result.details["channel_reload_plan"]["restart"] == 1
    assert result.details["control_plane_trace"]["action"] == "enable"
    assert result.details["control_plane_trace"]["capability_counts"]["tool_factories"] == 1
    assert (
        result.details["control_plane_trace"]["capability_counts"]["registered_tool_factories"] == 1
    )
    runtime_manager.set_plugin_enabled.assert_awaited_once_with(
        "plugin-a",
        enabled=True,
        tenant_id="tenant-1",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_install_plugin_returns_failure_result_without_raise() -> None:
    """Install failures should be returned as structured control-plane failures."""
    runtime_manager = SimpleNamespace(
        install_plugin=AsyncMock(return_value={"success": False, "error": "invalid requirement"}),
        is_plugin_enabled=lambda plugin_name, tenant_id=None: (
            plugin_name == "plugin-a" and tenant_id is None
        ),
    )
    registry = SimpleNamespace(
        list_channel_type_metadata=dict,
        list_tool_factories=lambda: {"plugin-a": object()},
        list_hooks=dict,
        list_commands=dict,
        list_services=dict,
        list_providers=dict,
    )
    service = PluginControlPlaneService(runtime_manager=runtime_manager, registry=registry)

    result = await service.install_plugin("bad-package")

    assert result.success is False
    assert result.message == "invalid requirement"
    assert result.details["control_plane_trace"]["action"] == "install"
    assert result.details["control_plane_trace"]["capability_counts"]["tool_factories"] == 1
    assert (
        result.details["control_plane_trace"]["capability_counts"]["registered_tool_factories"] == 1
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_control_plane_trace_excludes_disabled_memory_tool_factories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_manager = SimpleNamespace(
        set_plugin_enabled=AsyncMock(return_value=[]),
        is_plugin_enabled=lambda plugin_name, tenant_id=None: plugin_name == "memory-runtime",
    )
    registry = SimpleNamespace(
        list_channel_type_metadata=dict,
        list_tool_factories=lambda: {"memory-runtime": object()},
        list_hooks=dict,
        list_commands=dict,
        list_services=dict,
        list_providers=dict,
    )
    monkeypatch.setattr(
        "src.infrastructure.agent.plugins.control_plane.get_settings",
        lambda: SimpleNamespace(
            agent_memory_runtime_mode="plugin",
            agent_memory_tool_provider_mode="disabled",
        ),
    )
    service = PluginControlPlaneService(runtime_manager=runtime_manager, registry=registry)

    result = await service.set_plugin_enabled(
        "memory-runtime",
        enabled=False,
        tenant_id="tenant-1",
    )

    assert result.details["control_plane_trace"]["capability_counts"]["tool_factories"] == 0
    assert (
        result.details["control_plane_trace"]["capability_counts"]["registered_tool_factories"] == 1
    )
