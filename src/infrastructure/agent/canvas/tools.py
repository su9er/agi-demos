"""Canvas tools for the ReAct agent.

Provides @tool_define-based tools that let the agent create, update,
and delete canvas blocks during conversation. Events are emitted via
ctx.emit() following the standard pending-events pattern.
"""

from __future__ import annotations

import json
import logging

from src.infrastructure.agent.canvas.events import build_canvas_event_dict
from src.infrastructure.agent.canvas.manager import CanvasManager
from src.infrastructure.agent.tools.context import ToolContext
from src.infrastructure.agent.tools.define import tool_define
from src.infrastructure.agent.tools.result import ToolResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level DI (same pattern as todo_tools.py)
# ---------------------------------------------------------------------------

_canvas_manager: CanvasManager | None = None


def configure_canvas(manager: CanvasManager) -> None:
    """Inject the shared CanvasManager instance.

    Called during agent initialisation.
    """
    global _canvas_manager
    _canvas_manager = manager


def _get_manager() -> CanvasManager:
    if _canvas_manager is None:
        msg = "Canvas not configured. Call configure_canvas() first."
        raise RuntimeError(msg)
    return _canvas_manager


# ---------------------------------------------------------------------------
# canvas_create
# ---------------------------------------------------------------------------


@tool_define(
    name="canvas_create",
    description=(
        "Create a new canvas block to display rich content in the UI. "
        "Block types: code (syntax-highlighted code), table (structured data), "
        "chart (data visualisation), form (interactive input), image (media), "
        "markdown (formatted text), widget (custom interactive component). "
        "Returns the block ID for future updates."
    ),
    parameters={
        "type": "object",
        "properties": {
            "block_type": {
                "type": "string",
                "description": "Type of canvas block to create.",
                "enum": ["code", "table", "chart", "form", "image", "markdown", "widget"],
            },
            "title": {
                "type": "string",
                "description": "Title displayed above the block.",
            },
            "content": {
                "type": "string",
                "description": (
                    "Block content. For code: the source code. "
                    "For table: JSON array of rows. "
                    "For markdown: the markdown text. "
                    "For chart: JSON chart specification."
                ),
            },
            "metadata": {
                "type": "object",
                "description": (
                    "Optional metadata (e.g. language for code blocks, column headers for tables)."
                ),
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["block_type", "title", "content"],
    },
    permission=None,
    category="canvas",
)
async def canvas_create(
    ctx: ToolContext,
    *,
    block_type: str,
    title: str,
    content: str,
    metadata: dict[str, str] | None = None,
) -> ToolResult:
    """Create a new canvas block."""
    manager = _get_manager()

    try:
        block = manager.create_block(
            conversation_id=ctx.conversation_id,
            block_type=block_type,
            title=title,
            content=content,
            metadata=metadata,
        )
    except ValueError as exc:
        return ToolResult(output=json.dumps({"error": str(exc)}), is_error=True)

    await ctx.emit(
        build_canvas_event_dict(
            conversation_id=ctx.conversation_id,
            block_id=block.id,
            action="created",
            block=block,
        )
    )

    return ToolResult(
        output=json.dumps(
            {
                "success": True,
                "block_id": block.id,
                "block_type": block.block_type.value,
                "title": block.title,
                "version": block.version,
            }
        ),
        title=f"Canvas: {title}",
    )


# ---------------------------------------------------------------------------
# canvas_update
# ---------------------------------------------------------------------------


@tool_define(
    name="canvas_update",
    description=(
        "Update an existing canvas block's content, title, or metadata. "
        "Provide the block_id returned by canvas_create. "
        "Only the fields you provide will be changed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "block_id": {
                "type": "string",
                "description": "ID of the canvas block to update.",
            },
            "content": {
                "type": "string",
                "description": "New content for the block.",
            },
            "title": {
                "type": "string",
                "description": "New title for the block.",
            },
            "metadata": {
                "type": "object",
                "description": "Metadata fields to merge.",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["block_id"],
    },
    permission=None,
    category="canvas",
)
async def canvas_update(
    ctx: ToolContext,
    *,
    block_id: str,
    content: str | None = None,
    title: str | None = None,
    metadata: dict[str, str] | None = None,
) -> ToolResult:
    """Update an existing canvas block."""
    manager = _get_manager()

    try:
        block = manager.update_block(
            conversation_id=ctx.conversation_id,
            block_id=block_id,
            content=content,
            title=title,
            metadata=metadata,
        )
    except KeyError as exc:
        return ToolResult(output=json.dumps({"error": str(exc)}), is_error=True)

    await ctx.emit(
        build_canvas_event_dict(
            conversation_id=ctx.conversation_id,
            block_id=block.id,
            action="updated",
            block=block,
        )
    )

    return ToolResult(
        output=json.dumps(
            {
                "success": True,
                "block_id": block.id,
                "version": block.version,
            }
        ),
        title=f"Canvas updated: {block.title}",
    )


# ---------------------------------------------------------------------------
# canvas_delete
# ---------------------------------------------------------------------------


@tool_define(
    name="canvas_delete",
    description=(
        "Delete a canvas block from the UI. Provide the block_id returned by canvas_create."
    ),
    parameters={
        "type": "object",
        "properties": {
            "block_id": {
                "type": "string",
                "description": "ID of the canvas block to delete.",
            },
        },
        "required": ["block_id"],
    },
    permission=None,
    category="canvas",
)
async def canvas_delete(
    ctx: ToolContext,
    *,
    block_id: str,
) -> ToolResult:
    """Delete a canvas block."""
    manager = _get_manager()

    try:
        manager.delete_block(
            conversation_id=ctx.conversation_id,
            block_id=block_id,
        )
    except KeyError as exc:
        return ToolResult(output=json.dumps({"error": str(exc)}), is_error=True)

    await ctx.emit(
        build_canvas_event_dict(
            conversation_id=ctx.conversation_id,
            block_id=block_id,
            action="deleted",
            block=None,
        )
    )

    return ToolResult(
        output=json.dumps(
            {
                "success": True,
                "block_id": block_id,
                "deleted": True,
            }
        ),
        title="Canvas block deleted",
    )
