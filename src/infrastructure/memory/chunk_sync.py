"""Shared helpers for syncing memory rows into ``memory_chunks``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.application.services.memory_index_service import MemoryIndexService

if TYPE_CHECKING:
    from src.infrastructure.adapters.secondary.persistence.sql_chunk_repository import (
        SqlChunkRepository,
    )
    from src.infrastructure.graph.embedding.embedding_service import EmbeddingService

VALID_MEMORY_CHUNK_CATEGORIES = {"preference", "fact", "decision", "entity", "other"}


def normalize_memory_chunk_category(value: object) -> str:
    """Normalize a category value into the chunk schema's allowed set."""
    if isinstance(value, str) and value in VALID_MEMORY_CHUNK_CATEGORIES:
        return value
    return "other"


async def upsert_memory_chunks(
    chunk_repo: SqlChunkRepository,
    *,
    memory_id: str,
    content: str,
    project_id: str,
    category: str = "other",
    metadata: dict[str, Any] | None = None,
    embedding_service: EmbeddingService | None = None,
    max_tokens: int = 400,
) -> int:
    """Replace the searchable chunks for a memory row."""
    if not content or not content.strip():
        await delete_memory_chunks(
            chunk_repo,
            memory_id=memory_id,
            project_id=project_id,
        )
        return 0

    index_service = MemoryIndexService(chunk_repo, embedding_service)
    return await index_service.index_memory(
        memory_id=memory_id,
        content=content,
        project_id=project_id,
        category=normalize_memory_chunk_category(category),
        metadata=metadata,
        max_tokens=max_tokens,
    )


async def delete_memory_chunks(
    chunk_repo: SqlChunkRepository,
    *,
    memory_id: str,
    project_id: str,
) -> int:
    """Delete searchable chunks for a memory row."""
    return await chunk_repo.delete_by_source("memory", memory_id, project_id)
