"""Message Binding Repository Port - persistence interface for MessageBinding VOs.

Defines the Protocol that infrastructure adapters implement to persist and
query MessageBinding rules used by the MessageRouter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.domain.model.agent.binding_scope import BindingScope
    from src.domain.model.agent.message_binding import MessageBinding


@runtime_checkable
class MessageBindingRepositoryPort(Protocol):
    """Protocol for persisting and querying MessageBinding rules.

    Implementations store bindings in a durable backend (e.g. PostgreSQL)
    and support lookup by ID or by scope for bulk loading.
    """

    async def save(self, binding: MessageBinding) -> None:
        """Persist a message binding (insert or update).

        Args:
            binding: The MessageBinding to persist.
        """
        ...

    async def find_by_id(self, binding_id: str) -> MessageBinding | None:
        """Retrieve a single binding by its identifier.

        Args:
            binding_id: Unique binding identifier.

        Returns:
            The matching MessageBinding, or None if not found.
        """
        ...

    async def find_by_scope(
        self,
        scope: BindingScope,
        scope_id: str,
    ) -> list[MessageBinding]:
        """Retrieve all bindings matching a scope and scope_id.

        Args:
            scope: The BindingScope to filter by.
            scope_id: The scope entity identifier.

        Returns:
            List of matching bindings, possibly empty.
        """
        ...

    async def delete(self, binding_id: str) -> None:
        """Remove a binding by its identifier.

        If the binding does not exist, this is a no-op.

        Args:
            binding_id: Identifier of the binding to remove.
        """
        ...
