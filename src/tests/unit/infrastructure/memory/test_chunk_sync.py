from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.adapters.secondary.persistence.models import Base, MemoryChunk
from src.infrastructure.adapters.secondary.persistence.sql_chunk_repository import (
    SqlChunkRepository,
)
from src.infrastructure.memory.chunk_sync import delete_memory_chunks, upsert_memory_chunks


@pytest.fixture
async def chunk_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


def _chunk(
    *,
    project_id: str,
    source_type: str,
    source_id: str,
    content: str,
) -> MemoryChunk:
    return MemoryChunk(
        id=str(uuid4()),
        project_id=project_id,
        source_type=source_type,
        source_id=source_id,
        chunk_index=0,
        content=content,
        content_hash=str(uuid4()).replace("-", ""),
        category="fact",
    )


@pytest.mark.unit
class TestMemoryChunkSync:
    @pytest.mark.asyncio
    async def test_upsert_scopes_to_project_and_source_type(self, chunk_session: AsyncSession) -> None:
        repo = SqlChunkRepository(chunk_session)
        chunk_session.add_all(
            [
                _chunk(
                    project_id="proj-other",
                    source_type="memory",
                    source_id="shared-id",
                    content="keep other project",
                ),
                _chunk(
                    project_id="proj-main",
                    source_type="conversation",
                    source_id="shared-id",
                    content="keep other source type",
                ),
            ]
        )
        await chunk_session.commit()

        indexed = await upsert_memory_chunks(
            repo,
            memory_id="shared-id",
            content="line one\nline two\nline three",
            project_id="proj-main",
            category="decision",
            metadata={"source": "test"},
            embedding_service=None,
        )
        await chunk_session.commit()

        current = await repo.find_by_source("memory", "shared-id", "proj-main")
        other_project = await repo.find_by_source("memory", "shared-id", "proj-other")
        other_source = await repo.find_by_source("conversation", "shared-id", "proj-main")

        assert indexed == len(current)
        assert current
        assert all(chunk.category == "decision" for chunk in current)
        assert all(chunk.metadata_["source"] == "test" for chunk in current)
        assert len(other_project) == 1
        assert len(other_source) == 1

    @pytest.mark.asyncio
    async def test_delete_scopes_to_project_and_source_type(self, chunk_session: AsyncSession) -> None:
        repo = SqlChunkRepository(chunk_session)
        chunk_session.add_all(
            [
                _chunk(
                    project_id="proj-main",
                    source_type="memory",
                    source_id="shared-id",
                    content="delete me",
                ),
                _chunk(
                    project_id="proj-other",
                    source_type="memory",
                    source_id="shared-id",
                    content="keep other project",
                ),
                _chunk(
                    project_id="proj-main",
                    source_type="conversation",
                    source_id="shared-id",
                    content="keep other source type",
                ),
            ]
        )
        await chunk_session.commit()

        deleted = await delete_memory_chunks(
            repo,
            memory_id="shared-id",
            project_id="proj-main",
        )
        await chunk_session.commit()

        current = await repo.find_by_source("memory", "shared-id", "proj-main")
        other_project = await repo.find_by_source("memory", "shared-id", "proj-other")
        other_source = await repo.find_by_source("conversation", "shared-id", "proj-main")

        assert deleted == 1
        assert current == []
        assert len(other_project) == 1
        assert len(other_source) == 1

    @pytest.mark.asyncio
    async def test_upsert_does_not_dedup_against_other_memory_sources(
        self,
        chunk_session: AsyncSession,
    ) -> None:
        repo = SqlChunkRepository(chunk_session)
        chunk_session.add(
            _chunk(
                project_id="proj-main",
                source_type="memory",
                source_id="memory-a",
                content="same content across memories",
            )
        )
        await chunk_session.commit()

        indexed = await upsert_memory_chunks(
            repo,
            memory_id="memory-b",
            content="same content across memories",
            project_id="proj-main",
            category="fact",
            embedding_service=None,
        )
        await chunk_session.commit()

        memory_a_chunks = await repo.find_by_source("memory", "memory-a", "proj-main")
        memory_b_chunks = await repo.find_by_source("memory", "memory-b", "proj-main")

        assert indexed == len(memory_b_chunks)
        assert len(memory_a_chunks) == 1
        assert len(memory_b_chunks) == 1
