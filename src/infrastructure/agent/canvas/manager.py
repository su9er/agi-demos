"""Canvas manager for per-conversation canvas state.

Provides CRUD operations on canvas blocks scoped by conversation_id.
All mutations return the affected CanvasBlock (or None for deletes)
so the caller can emit SSE events.
"""

from __future__ import annotations

import logging
from typing import Any

from src.infrastructure.agent.canvas.models import (
    CanvasBlock,
    CanvasBlockType,
    CanvasState,
)

logger = logging.getLogger(__name__)


class CanvasManager:
    """Manages canvas block state for all active conversations.

    Each conversation has an independent :class:`CanvasState`.
    The manager is designed to be a singleton held by the agent runtime.
    """

    def __init__(self) -> None:
        super().__init__()
        self._conversations: dict[str, CanvasState] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_state(self, conversation_id: str) -> CanvasState:
        """Lazily initialise canvas state for a conversation."""
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = CanvasState()
        return self._conversations[conversation_id]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_block(
        self,
        conversation_id: str,
        block_type: str,
        title: str,
        content: str,
        metadata: dict[str, str] | None = None,
    ) -> CanvasBlock:
        """Create a new canvas block.

        Args:
            conversation_id: Scope of the canvas.
            block_type: One of CanvasBlockType values.
            title: Human-readable title.
            content: JSON-serialised content.
            metadata: Optional key-value metadata.

        Returns:
            The newly created CanvasBlock.

        Raises:
            ValueError: If block_type is invalid.
        """
        try:
            bt = CanvasBlockType(block_type)
        except ValueError:
            valid = [t.value for t in CanvasBlockType]
            msg = f"Invalid block_type '{block_type}'. Must be one of: {valid}"
            raise ValueError(msg) from None

        block = CanvasBlock(
            block_type=bt,
            title=title,
            content=content,
            metadata=metadata or {},
        )
        state = self._get_or_create_state(conversation_id)
        state.add(block)
        logger.info(
            "Canvas block created: id=%s type=%s conv=%s",
            block.id,
            block.block_type.value,
            conversation_id,
        )
        return block

    def update_block(
        self,
        conversation_id: str,
        block_id: str,
        content: str | None = None,
        title: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> CanvasBlock:
        """Update an existing canvas block (immutable replace).

        Args:
            conversation_id: Scope of the canvas.
            block_id: ID of the block to update.
            content: New content (optional).
            title: New title (optional).
            metadata: New metadata dict to merge (optional).

        Returns:
            The updated CanvasBlock with incremented version.

        Raises:
            KeyError: If block_id is not found.
        """
        state = self._get_or_create_state(conversation_id)
        existing = state.get(block_id)
        if existing is None:
            msg = f"Canvas block '{block_id}' not found in conversation '{conversation_id}'"
            raise KeyError(msg)

        updated = existing
        if content is not None:
            updated = updated.with_content(content)
        if title is not None:
            updated = updated.with_title(title)
        if metadata is not None:
            merged_meta = {**existing.metadata, **metadata}
            updated = CanvasBlock(
                id=updated.id,
                block_type=updated.block_type,
                title=updated.title,
                content=updated.content,
                metadata=merged_meta,
                version=updated.version,
            )

        state.add(updated)
        logger.info(
            "Canvas block updated: id=%s version=%d conv=%s",
            updated.id,
            updated.version,
            conversation_id,
        )
        return updated

    def delete_block(
        self,
        conversation_id: str,
        block_id: str,
    ) -> None:
        """Delete a canvas block.

        Args:
            conversation_id: Scope of the canvas.
            block_id: ID of the block to delete.

        Raises:
            KeyError: If block_id is not found.
        """
        state = self._get_or_create_state(conversation_id)
        removed = state.remove(block_id)
        if removed is None:
            msg = f"Canvas block '{block_id}' not found in conversation '{conversation_id}'"
            raise KeyError(msg)
        logger.info(
            "Canvas block deleted: id=%s conv=%s",
            block_id,
            conversation_id,
        )

    def get_blocks(self, conversation_id: str) -> list[CanvasBlock]:
        """Return all blocks for a conversation.

        Args:
            conversation_id: Scope of the canvas.

        Returns:
            List of CanvasBlock instances (empty if no state exists).
        """
        state = self._conversations.get(conversation_id)
        if state is None:
            return []
        return state.all_blocks()

    def get_block(self, conversation_id: str, block_id: str) -> CanvasBlock | None:
        """Return a single block by ID, or None."""
        state = self._conversations.get(conversation_id)
        if state is None:
            return None
        return state.get(block_id)

    def clear_conversation(self, conversation_id: str) -> None:
        """Remove all canvas state for a conversation."""
        _ = self._conversations.pop(conversation_id, None)

    def to_snapshot(self, conversation_id: str) -> list[dict[str, Any]]:
        """Serialise all blocks for a conversation as a list of dicts."""
        return [b.to_dict() for b in self.get_blocks(conversation_id)]
