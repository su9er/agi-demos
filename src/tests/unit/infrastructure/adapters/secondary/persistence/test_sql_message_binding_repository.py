"""Tests for SqlMessageBindingRepository."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.model.agent.binding_scope import BindingScope
from src.domain.model.agent.message_binding import MessageBinding
from src.infrastructure.adapters.secondary.persistence.sql_message_binding_repository import (
    SqlMessageBindingRepository,
)


@pytest.fixture
async def binding_repo(db_session: AsyncSession) -> SqlMessageBindingRepository:
    """Create a SqlMessageBindingRepository for testing."""
    return SqlMessageBindingRepository(db_session)


def make_message_binding(
    binding_id: str = "binding-1",
    agent_id: str = "agent-1",
    scope: BindingScope = BindingScope.CONVERSATION,
    scope_id: str = "conv-1",
    priority: int = 0,
    filter_pattern: str | None = None,
    is_active: bool = True,
) -> MessageBinding:
    """Factory for creating test MessageBinding value objects."""
    return MessageBinding(
        id=binding_id,
        agent_id=agent_id,
        scope=scope,
        scope_id=scope_id,
        priority=priority,
        filter_pattern=filter_pattern,
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# --- Save ---


class TestSave:
    """Tests for SqlMessageBindingRepository.save()."""

    @pytest.mark.asyncio
    async def test_save_creates_record(self, binding_repo: SqlMessageBindingRepository) -> None:
        binding = make_message_binding(binding_id="save-1", agent_id="agent-a")
        await binding_repo.save(binding)

        found = await binding_repo.find_by_id("save-1")
        assert found is not None
        assert found.id == "save-1"
        assert found.agent_id == "agent-a"
        assert found.scope == BindingScope.CONVERSATION
        assert found.scope_id == "conv-1"
        assert found.priority == 0
        assert found.filter_pattern is None
        assert found.is_active is True

    @pytest.mark.asyncio
    async def test_save_upsert_updates_existing(
        self, binding_repo: SqlMessageBindingRepository
    ) -> None:
        original = make_message_binding(binding_id="upsert-1", agent_id="agent-a", priority=0)
        await binding_repo.save(original)

        updated = make_message_binding(binding_id="upsert-1", agent_id="agent-b", priority=10)
        await binding_repo.save(updated)

        found = await binding_repo.find_by_id("upsert-1")
        assert found is not None
        assert found.agent_id == "agent-b"
        assert found.priority == 10

    @pytest.mark.asyncio
    async def test_save_with_filter_pattern(
        self, binding_repo: SqlMessageBindingRepository
    ) -> None:
        binding = make_message_binding(binding_id="filter-1", filter_pattern=r"^hello\s")
        await binding_repo.save(binding)

        found = await binding_repo.find_by_id("filter-1")
        assert found is not None
        assert found.filter_pattern == r"^hello\s"


# --- FindById ---


class TestFindById:
    """Tests for SqlMessageBindingRepository.find_by_id()."""

    @pytest.mark.asyncio
    async def test_find_by_id_returns_binding(
        self, binding_repo: SqlMessageBindingRepository
    ) -> None:
        binding = make_message_binding(binding_id="find-1", agent_id="agent-x")
        await binding_repo.save(binding)

        found = await binding_repo.find_by_id("find-1")
        assert found is not None
        assert found.id == "find-1"
        assert found.agent_id == "agent-x"

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_when_not_found(
        self, binding_repo: SqlMessageBindingRepository
    ) -> None:
        found = await binding_repo.find_by_id("nonexistent-id")
        assert found is None


# --- FindByScope ---


class TestFindByScope:
    """Tests for SqlMessageBindingRepository.find_by_scope()."""

    @pytest.mark.asyncio
    async def test_find_by_scope_returns_matching(
        self, binding_repo: SqlMessageBindingRepository
    ) -> None:
        b1 = make_message_binding(
            binding_id="scope-1",
            scope=BindingScope.PROJECT,
            scope_id="proj-1",
            priority=5,
        )
        b2 = make_message_binding(
            binding_id="scope-2",
            scope=BindingScope.PROJECT,
            scope_id="proj-1",
            priority=1,
        )
        b3 = make_message_binding(
            binding_id="scope-3",
            scope=BindingScope.TENANT,
            scope_id="tenant-1",
            priority=0,
        )
        await binding_repo.save(b1)
        await binding_repo.save(b2)
        await binding_repo.save(b3)

        results = await binding_repo.find_by_scope(BindingScope.PROJECT, "proj-1")
        assert len(results) == 2
        assert results[0].id == "scope-2"
        assert results[1].id == "scope-1"

    @pytest.mark.asyncio
    async def test_find_by_scope_returns_empty_when_no_match(
        self, binding_repo: SqlMessageBindingRepository
    ) -> None:
        results = await binding_repo.find_by_scope(BindingScope.DEFAULT, "no-match")
        assert results == []

    @pytest.mark.asyncio
    async def test_find_by_scope_ordered_by_priority(
        self, binding_repo: SqlMessageBindingRepository
    ) -> None:
        for i, prio in enumerate([10, 0, 5]):
            b = make_message_binding(
                binding_id=f"ord-{i}",
                scope=BindingScope.CONVERSATION,
                scope_id="conv-ord",
                priority=prio,
            )
            await binding_repo.save(b)

        results = await binding_repo.find_by_scope(BindingScope.CONVERSATION, "conv-ord")
        priorities = [r.priority for r in results]
        assert priorities == [0, 5, 10]


# --- Delete ---


class TestDelete:
    """Tests for SqlMessageBindingRepository.delete()."""

    @pytest.mark.asyncio
    async def test_delete_removes_record(self, binding_repo: SqlMessageBindingRepository) -> None:
        binding = make_message_binding(binding_id="del-1")
        await binding_repo.save(binding)

        await binding_repo.delete("del-1")

        found = await binding_repo.find_by_id("del-1")
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(
        self, binding_repo: SqlMessageBindingRepository
    ) -> None:
        await binding_repo.delete("does-not-exist")
