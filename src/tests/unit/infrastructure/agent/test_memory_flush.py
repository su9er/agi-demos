from unittest.mock import AsyncMock

import pytest

from src.infrastructure.agent.memory.flush import MemoryFlushService


@pytest.mark.unit
class TestMemoryFlushService:
    @pytest.mark.asyncio
    async def test_store_chunk_uses_metadata_field(self) -> None:
        service = MemoryFlushService(llm_client=AsyncMock(), session_factory=None)
        saved_chunks = []
        chunk_repo = AsyncMock()

        async def _save(chunk):  # type: ignore[no-untyped-def]
            saved_chunks.append(chunk)

        chunk_repo.save = AsyncMock(side_effect=_save)

        stored = await service._store_chunk(
            chunk_repo,
            content="remember this",
            category="fact",
            embedding=None,
            project_id="proj-1",
            conversation_id="conv-1",
        )

        assert stored is True
        assert saved_chunks[0].metadata_ == {"flush": True}
