"""Backward compatibility - re-exports from conversation subpackage."""

from src.domain.model.agent.conversation.attachment import (
    Attachment,
    AttachmentMetadata,
    AttachmentPurpose,
    AttachmentStatus,
    create_attachment_from_file,
)

__all__ = [
    "Attachment",
    "AttachmentMetadata",
    "AttachmentPurpose",
    "AttachmentStatus",
    "create_attachment_from_file",
]
