"""Default memory runtime used by agent lifecycle hooks."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, cast

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.services.memory_index_service import MemoryIndexService
from src.domain.events.agent_events import AgentMemoryCapturedEvent, AgentMemoryRecalledEvent

if TYPE_CHECKING:
    from src.domain.llm_providers.llm_types import LLMClient
    from src.infrastructure.graph.embedding.embedding_service import EmbeddingService


logger = logging.getLogger(__name__)

_memory_runtime_bg_tasks: set[asyncio.Task[Any]] = set()


class MemoryRecallService(Protocol):
    last_results: list[dict[str, Any]]
    last_search_ms: int

    async def recall(
        self,
        query: str,
        project_id: str,
        max_results: int = 3,
    ) -> str | None: ...


class MemoryCaptureService(Protocol):
    last_categories: list[str]

    async def capture(
        self,
        user_message: str,
        assistant_response: str,
        project_id: str,
        conversation_id: str = "unknown",
    ) -> int: ...


class MemoryFlushRuntimeService(Protocol):
    async def flush(
        self,
        conversation_messages: list[dict[str, Any]],
        project_id: str,
        conversation_id: str = "unknown",
    ) -> int: ...


class MemoryRuntimeProtocol(Protocol):
    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession] | None: ...

    async def recall_for_prompt(
        self,
        *,
        user_message: str,
        project_id: str,
    ) -> MemoryRuntimeResult: ...

    async def flush_on_context_overflow(
        self,
        *,
        conversation_context: list[dict[str, str]],
        project_id: str,
        conversation_id: str,
    ) -> MemoryRuntimeResult: ...

    async def capture_after_turn(
        self,
        *,
        user_message: str,
        final_content: str,
        project_id: str,
        conversation_id: str,
        conversation_context: list[dict[str, str]],
        success: bool,
        llm_client_override: object | None = None,
    ) -> MemoryRuntimeResult: ...


@dataclass
class MemoryRuntimeResult:
    """Structured result returned by memory runtime operations."""

    memory_context: str | None = None
    emitted_events: list[dict[str, Any]] = field(default_factory=list)
    stored_count: int = 0
    categories: list[str] = field(default_factory=list)


class DefaultMemoryRuntime:
    """Default implementation of durable memory behaviors for an agent turn."""

    def __init__(
        self,
        *,
        llm_client: LLMClient | None,
        graph_service: object | None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        redis_client: Redis | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._graph_service = graph_service
        self._session_factory = session_factory
        self._redis_client = redis_client
        self._embedding_service = getattr(graph_service, "embedder", None)
        self._cached_embedding = self._build_cached_embedding()
        self._memory_recall: MemoryRecallService | None = self._build_memory_recall()
        self._memory_capture: MemoryCaptureService | None = self._build_memory_capture()
        self._memory_flush: MemoryFlushRuntimeService | None = self._build_memory_flush()

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession] | None:
        """Expose the DB session factory for callers that need agent-level lookups."""
        return self._session_factory

    def _build_cached_embedding(self) -> object | None:
        if not self._embedding_service:
            return None
        try:
            from src.infrastructure.memory.cached_embedding import CachedEmbeddingService

            return CachedEmbeddingService(self._embedding_service, self._redis_client)
        except Exception as exc:
            logger.debug("Memory runtime cached embedding unavailable: %s", exc)
            return None

    def _build_memory_recall(self) -> MemoryRecallService | None:
        from src.infrastructure.agent.memory.recall import MemoryRecallPreprocessor

        chunk_search = None
        if self._cached_embedding is not None and self._session_factory is not None:
            try:
                from src.infrastructure.memory.chunk_search import ChunkHybridSearch

                chunk_search = ChunkHybridSearch(
                    cast("EmbeddingService", self._cached_embedding),
                    self._session_factory,
                )
            except Exception as exc:
                logger.debug("Memory runtime chunk search unavailable: %s", exc)

        return MemoryRecallPreprocessor(
            chunk_search=chunk_search,
            graph_search=self._graph_service,
        )

    def _build_memory_capture(self) -> MemoryCaptureService | None:
        if not self._llm_client or self._session_factory is None:
            return None
        try:
            from src.infrastructure.agent.memory.capture import MemoryCapturePostprocessor

            return cast(
                MemoryCaptureService,
                MemoryCapturePostprocessor(
                    llm_client=self._llm_client,
                    session_factory=self._session_factory,
                    embedding_service=cast("EmbeddingService | None", self._cached_embedding),
                ),
            )
        except Exception as exc:
            logger.debug("Memory runtime capture unavailable: %s", exc)
            return None

    def _build_memory_flush(self) -> MemoryFlushRuntimeService | None:
        if not self._llm_client or self._session_factory is None:
            return None
        try:
            from src.infrastructure.agent.memory.flush import MemoryFlushService

            return MemoryFlushService(
                llm_client=self._llm_client,
                embedding_service=cast("EmbeddingService | None", self._cached_embedding),
                session_factory=self._session_factory,
            )
        except Exception as exc:
            logger.debug("Memory runtime flush unavailable: %s", exc)
            return None

    async def recall_for_prompt(
        self,
        *,
        user_message: str,
        project_id: str,
    ) -> MemoryRuntimeResult:
        """Recall durable memory and format emitted events for prompt injection."""
        if self._memory_recall is None:
            return MemoryRuntimeResult()

        memory_context = await self._memory_recall.recall(user_message, project_id)
        if not memory_context or not self._memory_recall.last_results:
            return MemoryRuntimeResult(memory_context=memory_context)

        emitted_event = AgentMemoryRecalledEvent(
            memories=self._memory_recall.last_results,
            count=len(self._memory_recall.last_results),
            search_ms=self._memory_recall.last_search_ms,
        ).to_event_dict()
        return MemoryRuntimeResult(
            memory_context=memory_context,
            emitted_events=[cast(dict[str, Any], emitted_event)],
        )

    async def flush_on_context_overflow(
        self,
        *,
        conversation_context: list[dict[str, str]],
        project_id: str,
        conversation_id: str,
    ) -> MemoryRuntimeResult:
        """Flush durable memory before context compression drops prior turns."""
        if self._memory_flush is None or not conversation_context:
            return MemoryRuntimeResult()

        flushed = await self._memory_flush.flush(
            conversation_context,
            project_id,
            conversation_id,
        )
        if flushed <= 0:
            return MemoryRuntimeResult()

        emitted_event = AgentMemoryCapturedEvent(
            captured_count=flushed,
            categories=["flush"],
        ).to_event_dict()
        return MemoryRuntimeResult(
            emitted_events=[cast(dict[str, Any], emitted_event)],
            stored_count=flushed,
            categories=["flush"],
        )

    async def capture_after_turn(
        self,
        *,
        user_message: str,
        final_content: str,
        project_id: str,
        conversation_id: str,
        conversation_context: list[dict[str, str]],
        success: bool,
        llm_client_override: object | None = None,
    ) -> MemoryRuntimeResult:
        """Capture durable memory after a completed turn and queue indexing."""
        emitted_events: list[dict[str, Any]] = []
        stored_count = 0
        categories: list[str] = []

        if self._memory_capture is not None and success:
            capture_service = cast(Any, self._memory_capture)
            original_client = capture_service._llm_client
            if llm_client_override is not None:
                capture_service._llm_client = llm_client_override
            try:
                stored_count = await capture_service.capture(
                    user_message=user_message,
                    assistant_response=final_content or "",
                    project_id=project_id,
                    conversation_id=conversation_id or "unknown",
                )
                categories = list(capture_service.last_categories)
                if stored_count > 0:
                    emitted_event = AgentMemoryCapturedEvent(
                        captured_count=stored_count,
                        categories=categories,
                    ).to_event_dict()
                    emitted_events.append(cast(dict[str, Any], emitted_event))
            finally:
                capture_service._llm_client = original_client

        if success and conversation_id and conversation_context:
            task = asyncio.create_task(
                self._index_conversation_background(
                    conversation_context,
                    project_id,
                    conversation_id,
                )
            )
            _memory_runtime_bg_tasks.add(task)
            task.add_done_callback(_memory_runtime_bg_tasks.discard)

        return MemoryRuntimeResult(
            emitted_events=emitted_events,
            stored_count=stored_count,
            categories=categories,
        )

    async def _index_conversation_background(
        self,
        messages: list[dict[str, Any]],
        project_id: str,
        conversation_id: str,
    ) -> None:
        """Index a conversation transcript as searchable memory chunks."""
        if self._session_factory is None:
            return

        from src.infrastructure.adapters.secondary.persistence.sql_chunk_repository import (
            SqlChunkRepository,
        )

        session = self._session_factory()
        try:
            chunk_repo = SqlChunkRepository(session)
            index_service = MemoryIndexService(
                chunk_repo,
                cast("EmbeddingService | None", self._cached_embedding),
            )
            indexed = await index_service.index_conversation(
                conversation_id,
                messages,
                project_id,
            )
            if indexed > 0:
                await session.commit()
                logger.info(
                    "[MemoryRuntime] Indexed %d conversation chunks (conversation=%s)",
                    indexed,
                    conversation_id,
                )
        except Exception as exc:
            logger.debug("[MemoryRuntime] Background conversation indexing failed: %s", exc)
            await session.rollback()
        finally:
            await session.close()
