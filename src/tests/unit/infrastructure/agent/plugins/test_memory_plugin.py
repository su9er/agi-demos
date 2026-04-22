from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agent.memory.runtime import MemoryRuntimeResult
from src.infrastructure.agent.plugins.memory_plugin import register_builtin_memory_plugin
from src.infrastructure.agent.plugins.registry import AgentPluginRegistry, PluginToolBuildContext


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_plugin_before_prompt_build_delegates_to_runtime() -> None:
    registry = AgentPluginRegistry()
    register_builtin_memory_plugin(registry)
    runtime = SimpleNamespace(
        recall_for_prompt=AsyncMock(
            return_value=MemoryRuntimeResult(
                memory_context="remembered context",
                emitted_events=[{"type": "memory_recalled", "data": {"count": 1}}],
            )
        )
    )

    result = await registry.apply_hook(
        "before_prompt_build",
        payload={
            "memory_runtime": runtime,
            "project_id": "proj-1",
            "user_message": "hello",
        },
    )

    assert result.payload["memory_context"] == "remembered context"
    assert result.payload["emitted_events"] == [{"type": "memory_recalled", "data": {"count": 1}}]
    runtime.recall_for_prompt.assert_awaited_once_with(
        user_message="hello",
        project_id="proj-1",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_plugin_tool_factory_builds_memory_tools() -> None:
    registry = AgentPluginRegistry()
    register_builtin_memory_plugin(registry)

    configure_get = MagicMock()
    configure_create = MagicMock()
    configure_search = MagicMock()
    memory_search_tool = MagicMock(name="memory_search_tool")
    memory_get_tool = MagicMock(name="memory_get_tool")
    memory_create_tool = MagicMock(name="memory_create_tool")
    memory_update_tool = MagicMock(name="memory_update_tool")
    memory_delete_tool = MagicMock(name="memory_delete_tool")

    with (
        patch(
            "src.infrastructure.agent.tools.memory_tools.configure_memory_get",
            configure_get,
        ),
        patch(
            "src.infrastructure.agent.tools.memory_tools.configure_memory_create",
            configure_create,
        ),
        patch(
            "src.infrastructure.agent.tools.memory_tools.configure_memory_search",
            configure_search,
        ),
        patch(
            "src.infrastructure.agent.tools.memory_tools.memory_search_tool",
            memory_search_tool,
        ),
        patch(
            "src.infrastructure.agent.tools.memory_tools.memory_get_tool",
            memory_get_tool,
        ),
        patch(
            "src.infrastructure.agent.tools.memory_tools.memory_create_tool",
            memory_create_tool,
        ),
        patch(
            "src.infrastructure.agent.tools.memory_tools.memory_update_tool",
            memory_update_tool,
        ),
        patch(
            "src.infrastructure.agent.tools.memory_tools.memory_delete_tool",
            memory_delete_tool,
        ),
        patch(
            "src.infrastructure.memory.cached_embedding.CachedEmbeddingService",
            return_value="cached-embedder",
        ),
        patch(
            "src.infrastructure.memory.chunk_search.ChunkHybridSearch",
            return_value="chunk-search",
        ),
    ):
        plugin_tools, diagnostics = await registry.build_tools(
            PluginToolBuildContext(
                tenant_id="tenant-1",
                project_id="proj-1",
                base_tools={},
                graph_service=SimpleNamespace(embedder=object()),
                redis_client=None,
                session_factory=MagicMock(name="session-factory"),
            )
        )

    assert configure_get.called
    assert configure_create.called
    assert configure_search.call_args.kwargs["chunk_search"] == "chunk-search"
    assert plugin_tools == {
        "memory_search": memory_search_tool,
        "memory_get": memory_get_tool,
        "memory_create": memory_create_tool,
        "memory_update": memory_update_tool,
        "memory_delete": memory_delete_tool,
    }
    assert any(item.code == "plugin_loaded" for item in diagnostics)
