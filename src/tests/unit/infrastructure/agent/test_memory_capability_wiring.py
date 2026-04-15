from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestProjectMemoryCapabilityInit:
    @pytest.mark.asyncio
    async def test_enables_recall_capture_and_flush_without_redis(self) -> None:
        from src.infrastructure.agent.core.project_react_agent import ProjectReActAgent

        agent = ProjectReActAgent.__new__(ProjectReActAgent)
        agent.config = SimpleNamespace(
            tenant_id="tenant-1",
            project_id="proj-1",
            agent_mode="default",
        )
        agent._get_session_factory = MagicMock(return_value="session-factory")
        graph_service = SimpleNamespace(embedder=object())

        with (
            patch(
                "src.infrastructure.memory.cached_embedding.CachedEmbeddingService",
                side_effect=lambda embedding_service, redis_client: {
                    "embedding_service": embedding_service,
                    "redis_client": redis_client,
                },
            ) as cached_cls,
            patch(
                "src.infrastructure.memory.chunk_search.ChunkHybridSearch",
                return_value="chunk-search",
            ),
            patch(
                "src.infrastructure.agent.memory.recall.MemoryRecallPreprocessor",
                return_value="recall",
            ),
            patch(
                "src.infrastructure.agent.memory.capture.MemoryCapturePostprocessor",
                return_value="capture",
            ),
            patch(
                "src.infrastructure.agent.memory.flush.MemoryFlushService",
                return_value="flush",
            ),
        ):
            memory_recall, memory_capture, memory_flush = agent._init_memory_services(
                graph_service,
                None,
                object(),
            )

        assert memory_recall == "recall"
        assert memory_capture == "capture"
        assert memory_flush == "flush"
        assert all(call.args[1] is None for call in cached_cls.call_args_list)

    @pytest.mark.asyncio
    async def test_enables_capture_and_flush_without_embeddings(self) -> None:
        from src.infrastructure.agent.core.project_react_agent import ProjectReActAgent

        agent = ProjectReActAgent.__new__(ProjectReActAgent)
        agent.config = SimpleNamespace(
            tenant_id="tenant-1",
            project_id="proj-1",
            agent_mode="default",
        )
        agent._get_session_factory = MagicMock(return_value="session-factory")
        graph_service = SimpleNamespace(embedder=None)

        with (
            patch(
                "src.infrastructure.agent.memory.capture.MemoryCapturePostprocessor",
                return_value="capture",
            ),
            patch(
                "src.infrastructure.agent.memory.flush.MemoryFlushService",
                return_value="flush",
            ),
        ):
            memory_recall, memory_capture, memory_flush = agent._init_memory_services(
                graph_service,
                None,
                object(),
            )

        assert memory_recall is None
        assert memory_capture == "capture"
        assert memory_flush == "flush"


@pytest.mark.unit
class TestMemoryToolWiring:
    def test_add_memory_tools_configures_search_without_redis(self) -> None:
        tools: dict[str, object] = {}
        graph_service = SimpleNamespace(embedder=object())
        configure_get = MagicMock()
        configure_create = MagicMock()
        configure_search = MagicMock()
        memory_update_tool = MagicMock()
        memory_delete_tool = MagicMock()

        with (
            patch(
                "src.infrastructure.adapters.secondary.persistence.database.async_session_factory",
                MagicMock(name="session-factory"),
            ),
            patch(
                "src.infrastructure.memory.cached_embedding.CachedEmbeddingService",
                return_value="cached-embedder",
            ),
            patch(
                "src.infrastructure.memory.chunk_search.ChunkHybridSearch",
                return_value="chunk-search",
            ),
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
                "src.infrastructure.agent.tools.memory_tools.memory_update_tool",
                memory_update_tool,
            ),
            patch(
                "src.infrastructure.agent.tools.memory_tools.memory_delete_tool",
                memory_delete_tool,
            ),
        ):
            from src.infrastructure.agent.state.agent_worker_state import _add_memory_tools

            _add_memory_tools(
                tools,
                project_id="proj-1",
                graph_service=graph_service,
                redis_client=None,
                tenant_id="tenant-1",
            )

        assert configure_get.called
        assert configure_create.called
        assert configure_search.call_args.kwargs["chunk_search"] == "chunk-search"
        assert tools["memory_update"] is memory_update_tool
        assert tools["memory_delete"] is memory_delete_tool

    def test_add_memory_tools_keeps_crud_when_search_is_unavailable(self) -> None:
        tools: dict[str, object] = {}
        graph_service = SimpleNamespace(embedder=None)
        configure_get = MagicMock()
        configure_create = MagicMock()
        configure_search = MagicMock()
        memory_update_tool = MagicMock()
        memory_delete_tool = MagicMock()

        with (
            patch(
                "src.infrastructure.adapters.secondary.persistence.database.async_session_factory",
                MagicMock(name="session-factory"),
            ),
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
                "src.infrastructure.agent.tools.memory_tools.memory_update_tool",
                memory_update_tool,
            ),
            patch(
                "src.infrastructure.agent.tools.memory_tools.memory_delete_tool",
                memory_delete_tool,
            ),
        ):
            from src.infrastructure.agent.state.agent_worker_state import _add_memory_tools

            _add_memory_tools(
                tools,
                project_id="proj-1",
                graph_service=graph_service,
                redis_client=None,
                tenant_id="tenant-1",
            )

        assert configure_get.called
        assert configure_create.called
        assert configure_search.call_args.kwargs["chunk_search"] is None
        assert tools["memory_update"] is memory_update_tool
        assert tools["memory_delete"] is memory_delete_tool
