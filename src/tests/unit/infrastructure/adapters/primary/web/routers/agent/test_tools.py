from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.adapters.primary.web.routers.agent.tools import (
    get_tool_capabilities,
    list_tools,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_tools_omits_memory_tools_when_provider_globally_disabled() -> None:
    runtime_manager = MagicMock()
    runtime_manager.ensure_loaded = AsyncMock(return_value=[])

    with (
        patch(
            "src.infrastructure.adapters.primary.web.routers.agent.tools.get_settings",
            return_value=SimpleNamespace(
                agent_memory_runtime_mode="plugin",
                agent_memory_tool_provider_mode="disabled",
            ),
        ),
        patch(
            "src.infrastructure.agent.plugins.manager.get_plugin_runtime_manager",
            return_value=runtime_manager,
        ),
    ):
        response = await list_tools(
            current_user=SimpleNamespace(tenant_id="tenant-1"),
        )

    tool_names = {tool.name for tool in response.tools}
    assert "memory_search" not in tool_names
    assert "memory_create" not in tool_names
    assert {"entity_lookup", "episode_retrieval", "graph_query", "summary"}.issubset(tool_names)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_tool_capabilities_includes_builtin_runtime_plugins() -> None:
    runtime_manager = MagicMock()
    runtime_manager.ensure_loaded = AsyncMock(return_value=[])
    runtime_manager.list_plugins.return_value = (
        [
            {"name": "sisyphus-runtime", "enabled": True},
            {"name": "memory-runtime", "enabled": True},
        ],
        [],
    )
    runtime_manager.is_plugin_enabled.return_value = True
    registry = MagicMock()
    registry.list_tool_factories.return_value = {"memory-runtime": object()}
    registry.list_channel_type_metadata.return_value = {}
    registry.list_hooks.return_value = {
        "before_response": {"sisyphus-runtime": (30, object())},
        "before_prompt_build": {"memory-runtime": (25, object())},
        "after_turn_complete": {"memory-runtime": (25, object())},
    }
    registry.list_commands.return_value = {}
    registry.list_services.return_value = {"memory-runtime": ("memory-runtime", object())}
    registry.list_providers.return_value = {}

    with (
        patch(
            "src.infrastructure.agent.plugins.manager.get_plugin_runtime_manager",
            return_value=runtime_manager,
        ),
        patch(
            "src.infrastructure.agent.plugins.registry.get_plugin_registry",
            return_value=registry,
        ),
    ):
        response = await get_tool_capabilities(
            current_user=SimpleNamespace(tenant_id="tenant-1"),
        )

    assert response.plugin_runtime.plugins_total == 2
    assert response.plugin_runtime.plugins_enabled == 2
    assert response.plugin_runtime.tool_factories == 1
    assert response.plugin_runtime.registered_tool_factories == 1
    assert response.plugin_runtime.hook_handlers == 3
    assert response.plugin_runtime.services == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_tool_capabilities_excludes_memory_tools_when_memory_plugin_disabled() -> None:
    runtime_manager = MagicMock()
    runtime_manager.ensure_loaded = AsyncMock(return_value=[])
    runtime_manager.list_plugins.return_value = (
        [
            {"name": "sisyphus-runtime", "enabled": True},
            {"name": "memory-runtime", "enabled": False},
        ],
        [],
    )
    runtime_manager.is_plugin_enabled.return_value = False

    registry = MagicMock()
    registry.list_tool_factories.return_value = {"memory-runtime": object()}
    registry.list_channel_type_metadata.return_value = {}
    registry.list_hooks.return_value = {}
    registry.list_commands.return_value = {}
    registry.list_services.return_value = {}
    registry.list_providers.return_value = {}

    with (
        patch(
            "src.infrastructure.adapters.primary.web.routers.agent.tools.get_settings",
            return_value=SimpleNamespace(
                agent_memory_runtime_mode="plugin",
                agent_memory_tool_provider_mode="plugin",
            ),
        ),
        patch(
            "src.infrastructure.agent.plugins.manager.get_plugin_runtime_manager",
            return_value=runtime_manager,
        ),
        patch(
            "src.infrastructure.agent.plugins.registry.get_plugin_registry",
            return_value=registry,
        ),
    ):
        response = await get_tool_capabilities(
            current_user=SimpleNamespace(tenant_id="tenant-1"),
        )

    assert response.total_tools == 4
    assert response.core_tools == 4
    assert response.plugin_runtime.plugins_total == 2
    assert response.plugin_runtime.tool_factories == 0
    assert response.plugin_runtime.registered_tool_factories == 1
