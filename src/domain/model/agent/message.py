"""Backward compatibility - re-exports from conversation subpackage."""

from src.domain.model.agent.conversation.message import (
    Message,
    MessageRole,
    MessageType,
    ToolCall,
    ToolResult,
)

__all__ = [
    "Message",
    "MessageRole",
    "MessageType",
    "ToolCall",
    "ToolResult",
]
