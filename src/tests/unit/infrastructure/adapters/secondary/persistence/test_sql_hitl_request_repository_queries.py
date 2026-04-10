"""Query-shape tests for SqlHITLRequestRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.model.agent.hitl_request import HITLRequestStatus
from src.infrastructure.adapters.secondary.persistence.sql_hitl_request_repository import (
    SqlHITLRequestRepository,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_pending_by_project_for_user_prefers_request_user_binding() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=result)

    repo = SqlHITLRequestRepository(session)

    await repo.get_pending_by_project_for_user("tenant-1", "project-1", "user-1")

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()

    assert "hitl_requests.user_id = :user_id_1" in str(compiled)
    assert "conversations.user_id = :user_id_2" in str(compiled)
    assert compiled.params["user_id_1"] == "user-1"
    assert compiled.params["user_id_2"] == "user-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mark_completed_with_lease_owner_requires_processing_state() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    repo = SqlHITLRequestRepository(session)

    await repo.mark_completed("req-1", lease_owner="worker-1")

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()

    assert HITLRequestStatus.ANSWERED.value not in compiled.params.values()
    assert HITLRequestStatus.PROCESSING.value in compiled.params.values()
    assert "worker-1" in compiled.params.values()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reopen_pending_preserves_existing_expiry() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    repo = SqlHITLRequestRepository(session)

    await repo.reopen_pending("req-1")

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()

    assert "expires_at" not in compiled.params
