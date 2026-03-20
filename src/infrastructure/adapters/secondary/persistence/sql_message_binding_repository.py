"""SQL repository for MessageBinding persistence."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.model.agent.binding_scope import BindingScope
from src.domain.model.agent.message_binding import MessageBinding

logger = logging.getLogger(__name__)


class SqlMessageBindingRepository:
    """SQLAlchemy implementation of MessageBindingRepositoryPort.

    Persists MessageBinding value objects to the ``message_bindings`` table.
    Uses ``flush()`` internally; the caller is responsible for ``commit()``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, binding: MessageBinding) -> None:
        db_model = self._to_db(binding)
        merged = await self._session.merge(db_model)
        self._session.add(merged)
        await self._session.flush()

    async def find_by_id(self, binding_id: str) -> MessageBinding | None:
        from src.infrastructure.adapters.secondary.persistence.models import (
            MessageBindingModel,
        )

        result = await self._session.execute(
            select(MessageBindingModel).where(MessageBindingModel.id == binding_id)
        )
        db_binding = result.scalar_one_or_none()
        return self._to_domain(db_binding) if db_binding else None

    async def find_by_scope(
        self,
        scope: BindingScope,
        scope_id: str,
    ) -> list[MessageBinding]:
        from src.infrastructure.adapters.secondary.persistence.models import (
            MessageBindingModel,
        )

        result = await self._session.execute(
            select(MessageBindingModel)
            .where(MessageBindingModel.scope == scope.value)
            .where(MessageBindingModel.scope_id == scope_id)
            .order_by(MessageBindingModel.priority.asc())
        )
        db_bindings = result.scalars().all()
        return [self._to_domain(b) for b in db_bindings]

    async def delete(self, binding_id: str) -> None:
        from src.infrastructure.adapters.secondary.persistence.models import (
            MessageBindingModel,
        )

        result = await self._session.execute(
            select(MessageBindingModel).where(MessageBindingModel.id == binding_id)
        )
        db_binding = result.scalar_one_or_none()
        if db_binding is not None:
            await self._session.delete(db_binding)
            await self._session.flush()

    @staticmethod
    def _to_domain(db_binding: object) -> MessageBinding:
        from src.infrastructure.adapters.secondary.persistence.models import (
            MessageBindingModel,
        )

        assert isinstance(db_binding, MessageBindingModel)
        return MessageBinding(
            id=db_binding.id,
            agent_id=db_binding.agent_id,
            scope=BindingScope(db_binding.scope),
            scope_id=db_binding.scope_id,
            priority=db_binding.priority,
            filter_pattern=db_binding.filter_pattern,
            is_active=db_binding.is_active,
            created_at=db_binding.created_at,
            updated_at=db_binding.updated_at,
        )

    @staticmethod
    def _to_db(binding: MessageBinding) -> object:
        from src.infrastructure.adapters.secondary.persistence.models import (
            MessageBindingModel,
        )

        return MessageBindingModel(
            id=binding.id,
            agent_id=binding.agent_id,
            scope=binding.scope.value,
            scope_id=binding.scope_id,
            priority=binding.priority,
            filter_pattern=binding.filter_pattern,
            is_active=binding.is_active,
            created_at=binding.created_at,
            updated_at=binding.updated_at,
        )
