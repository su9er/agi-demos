"""Tests for SqlAgentBindingRepository stale-read behavior."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.model.agent.agent_binding import AgentBinding
from src.infrastructure.adapters.secondary.persistence.models import AgentDefinitionModel
from src.infrastructure.adapters.secondary.persistence.sql_binding_repository import (
    SqlAgentBindingRepository,
)


@pytest.fixture
async def binding_repo(db_session: AsyncSession) -> SqlAgentBindingRepository:
    """Create a binding repository with a backing agent definition."""
    db_session.add(
        AgentDefinitionModel(
            id="agent-binding-test",
            tenant_id="tenant-binding",
            name="binding-agent",
            display_name="Binding Agent",
            system_prompt="You are a binding test agent.",
            trigger_description="Binding trigger",
            allowed_tools=[],
            allowed_skills=[],
            allowed_mcp_servers=[],
            source="database",
        )
    )
    await db_session.flush()
    return SqlAgentBindingRepository(db_session)


def _make_binding(binding_id: str, *, enabled: bool = True) -> AgentBinding:
    return AgentBinding(
        id=binding_id,
        tenant_id="tenant-binding",
        agent_id="agent-binding-test",
        channel_type="websocket",
        channel_id="channel-1",
        account_id="account-1",
        peer_id="peer-1",
        priority=1,
        enabled=enabled,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_get_by_id_refreshes_existing_identity_map_rows(
    binding_repo: SqlAgentBindingRepository,
    db_session: AsyncSession,
) -> None:
    """Re-reading with the same session should observe external updates."""
    binding = _make_binding("binding-refresh-1")
    await binding_repo.create(binding)
    await db_session.commit()

    first = await binding_repo.get_by_id("binding-refresh-1")
    assert first is not None
    assert first.enabled is True

    session_factory = async_sessionmaker(
        db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as other_session:
        other_repo = SqlAgentBindingRepository(other_session)
        updated = await other_repo.set_enabled("binding-refresh-1", False)
        assert updated.enabled is False
        await other_session.commit()

    refreshed = await binding_repo.get_by_id("binding-refresh-1")
    assert refreshed is not None
    assert refreshed.enabled is False
