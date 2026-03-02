"""Artifact handling for session processor.

Extracted from processor.py -- handles artifact extraction from tool
outputs, sanitization of binary data, S3 uploads, and canvas-displayable
content detection.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from src.domain.events.agent_events import (
    AgentArtifactCreatedEvent,
    AgentArtifactOpenEvent,
    AgentDomainEvent,
)
from src.infrastructure.adapters.secondary.sandbox.artifact_integration import (
    extract_artifacts_from_mcp_result,
)

if TYPE_CHECKING:
    from src.application.services.artifact_service import ArtifactService

logger = logging.getLogger(__name__)

# Module-level set to prevent background upload tasks from being GC'd.
_artifact_bg_tasks: set[asyncio.Task[Any]] = set()

# -----------------------------------------------------------------------
# Module-level helpers (previously in processor.py top-level scope)
# -----------------------------------------------------------------------


def strip_artifact_binary_data(result: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of an artifact result with binary/base64 data removed.

    The artifact binary content is handled separately by ``process_tool_artifacts``
    and must not leak into the ``AgentObserveEvent.result`` field.  Keeping it
    there causes the JSON payload persisted to Redis and PostgreSQL to be
    extremely large, which can fail the entire event-persistence transaction
    and lose all conversation history.
    """
    cleaned = {**result}
    if "artifact" in cleaned and isinstance(cleaned["artifact"], dict):
        artifact = {**cleaned["artifact"]}
        artifact.pop("data", None)
        cleaned["artifact"] = artifact
    # Also strip base64 from embedded MCP content items
    if "content" in cleaned and isinstance(cleaned["content"], list):
        stripped_content = []
        for item in cleaned["content"]:
            if isinstance(item, dict) and item.get("type") in ("image", "resource"):
                item = {**item}
                item.pop("data", None)
            stripped_content.append(item)
        cleaned["content"] = stripped_content
    return cleaned


# Canvas-displayable MIME type mapping
_CANVAS_MIME_MAP: dict[str, str] = {
    "text/html": "preview",
    "text/markdown": "markdown",
    "text/csv": "data",
    "application/json": "data",
    "application/xml": "data",
    "text/xml": "data",
}


def get_canvas_content_type(mime_type: str, filename: str) -> str | None:
    """Determine canvas content type for a given MIME type and filename."""
    if mime_type in _CANVAS_MIME_MAP:
        return _CANVAS_MIME_MAP[mime_type]
    if mime_type.startswith("text/"):
        return "code"
    # Check common code extensions
    code_exts = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".sh",
        ".bash",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".sql",
        ".css",
        ".scss",
        ".less",
        ".vue",
        ".svelte",
    }
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in code_exts:
        return "code"
    return None


_LANG_EXT_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".md": "markdown",
    ".xml": "xml",
    ".toml": "toml",
}


def get_language_from_filename(filename: str) -> str | None:
    """Get language identifier from filename extension."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _LANG_EXT_MAP.get(ext)


# -----------------------------------------------------------------------
# ArtifactHandler class
# -----------------------------------------------------------------------

_MAX_TOOL_OUTPUT_BYTES = 30_000

# Regex matching long base64-like sequences (256+ chars of [A-Za-z0-9+/=])
_BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/=]{256,}")


class ArtifactHandler:
    """Handles artifact extraction, sanitization, and upload from tool outputs.

    Parameters
    ----------
    artifact_service:
        The artifact service used for create_artifact calls.
    langfuse_context:
        Observability context dict providing project_id, tenant_id, etc.
    """

    def __init__(
        self,
        artifact_service: ArtifactService | None,
        langfuse_context: dict[str, Any] | None,
    ) -> None:
        self._artifact_service = artifact_service
        self._langfuse_context = langfuse_context

    def set_langfuse_context(self, ctx: dict[str, Any] | None) -> None:
        """Update langfuse context (set per-process call)."""
        self._langfuse_context = ctx

    # ------------------------------------------------------------------
    # Sanitization
    # ------------------------------------------------------------------

    @staticmethod
    def sanitize_tool_output(output: str) -> str:
        """Sanitize tool output to prevent binary/base64 data from entering LLM context.

        Applies two defensive filters:
        1. Replace long base64-like sequences with a placeholder.
        2. Truncate output exceeding _MAX_TOOL_OUTPUT_BYTES.
        """
        if not output:
            return output

        # Strip embedded base64 blobs
        sanitized = _BASE64_PATTERN.sub("[binary data omitted]", output)

        # Hard size cap
        encoded = sanitized.encode("utf-8", errors="replace")
        if len(encoded) > _MAX_TOOL_OUTPUT_BYTES:
            sanitized = encoded[:_MAX_TOOL_OUTPUT_BYTES].decode("utf-8", errors="ignore")
            sanitized += "\n... [output truncated]"

        return sanitized

    # ------------------------------------------------------------------
    # Artifact processing
    # ------------------------------------------------------------------

    async def process_tool_artifacts(  # noqa: C901, PLR0911, PLR0912, PLR0915
        self,
        tool_name: str,
        result: Any,  # noqa: ANN401
        tool_execution_id: str | None = None,
    ) -> AsyncIterator[AgentDomainEvent]:
        """Process tool result and extract any artifacts (images, files, etc.).

        This method:
        1. Extracts image/resource content from MCP-style results
        2. Uploads artifacts to storage via ArtifactService
        3. Emits artifact_created events for frontend display

        Args:
            tool_name: Name of the tool that produced the result
            result: Tool execution result (may contain images/resources)
            tool_execution_id: ID of the tool execution

        Yields:
            AgentArtifactCreatedEvent for each artifact created
        """
        logger.warning(
            f"[ArtifactUpload] Processing tool={tool_name}, "
            f"has_service={self._artifact_service is not None}, "
            f"result_type={type(result).__name__}"
        )

        if not self._artifact_service:
            logger.warning("[ArtifactUpload] No artifact_service configured, skipping")
            return

        # Get context from langfuse context
        ctx = self._langfuse_context or {}
        project_id = ctx.get("project_id")
        tenant_id = ctx.get("tenant_id")
        conversation_id = ctx.get("conversation_id")
        sandbox_id: str | None = ctx.get("sandbox_id")

        if not project_id or not tenant_id:
            logger.warning(
                f"[ArtifactUpload] Missing context: project_id={project_id}, tenant_id={tenant_id}"
            )
            return

        # Check if result contains MCP-style content
        if not isinstance(result, dict):
            return

        has_artifact = result.get("artifact") is not None
        if has_artifact:
            has_data = result["artifact"].get("data") is not None
            logger.warning(
                f"[ArtifactUpload] tool={tool_name}, has_data={has_data}, "
                f"encoding={result['artifact'].get('encoding')}"
            )

        # Check for export_artifact tool result which has special 'artifact' field
        if result.get("artifact"):
            artifact_info = result["artifact"]
            try:
                import base64

                # Get file content
                encoding = artifact_info.get("encoding", "utf-8")
                if encoding == "base64":
                    # Binary file - get data from artifact info or image content
                    data = artifact_info.get("data")
                    if not data:
                        # Check for image content
                        for item in result.get("content", []):
                            if item.get("type") == "image":
                                data = item.get("data")
                                break
                    if data:
                        file_content = base64.b64decode(data)
                        logger.warning(
                            f"[ArtifactUpload] Decoded {len(file_content)} bytes from base64"
                        )
                    else:
                        logger.warning("[ArtifactUpload] base64 encoding but no data found")
                        return
                else:
                    # Text file - get from content
                    content = result.get("content", [])
                    if content:
                        first_item = content[0] if content else {}
                        text = (
                            first_item.get("text", "")
                            if isinstance(first_item, dict)
                            else str(first_item)
                        )
                        if not text:
                            logger.warning("export_artifact returned empty text content")
                            return
                        file_content = text.encode("utf-8")
                    else:
                        logger.warning("export_artifact returned no content")
                        return

                # Detect MIME type for the artifact_created event
                from src.application.services.artifact_service import (
                    detect_mime_type,
                    get_category_from_mime,
                )

                filename = artifact_info.get("filename", "exported_file")
                mime_type = detect_mime_type(filename)
                category = get_category_from_mime(mime_type)
                artifact_id = str(uuid.uuid4())

                # Yield artifact_created event IMMEDIATELY so the frontend
                # knows about the artifact even if the upload is slow.
                yield AgentArtifactCreatedEvent(
                    artifact_id=artifact_id,
                    filename=filename,
                    mime_type=mime_type,
                    category=category.value,
                    size_bytes=len(file_content),
                    url=None,
                    preview_url=None,
                    tool_execution_id=tool_execution_id,
                    source_tool=tool_name,
                    source_path=artifact_info.get("path"),
                )

                # Emit artifact_open for canvas-displayable content
                canvas_type = get_canvas_content_type(mime_type, filename)
                if canvas_type and len(file_content) < 500_000:
                    try:
                        text_content = file_content.decode("utf-8")
                        yield AgentArtifactOpenEvent(
                            artifact_id=artifact_id,
                            title=filename,
                            content=text_content,
                            content_type=canvas_type,
                            language=get_language_from_filename(filename),
                        )
                    except (UnicodeDecodeError, ValueError):
                        pass  # Binary content, skip canvas open

                # Schedule background upload via ArtifactService.
                logger.warning(
                    f"[ArtifactUpload] Scheduling background upload: filename={filename}, "
                    f"size={len(file_content)}, project_id={project_id}"
                )

                _schedule_artifact_upload(
                    artifact_service=self._artifact_service,
                    file_content=file_content,
                    filename=filename,
                    project_id=project_id,
                    tenant_id=tenant_id,
                    tool_execution_id=tool_execution_id or "",
                    conversation_id=conversation_id or "",
                    tool_name=tool_name,
                    artifact_id=artifact_id,
                    source_path=artifact_info.get("path"),
                    sandbox_id=sandbox_id,
                )
                return

            except Exception as e:
                import traceback

                logger.error(
                    f"Failed to process export_artifact result: {e}\n"
                    f"Artifact info: {artifact_info}\n"
                    f"Traceback: {traceback.format_exc()}"
                )

        # Check for batch_export_artifacts results
        batch_results = result.get("results")
        if batch_results and isinstance(batch_results, list) and len(batch_results) > 0:
            import base64 as b64

            from src.application.services.artifact_service import (
                detect_mime_type,
                get_category_from_mime,
            )

            for batch_item in batch_results:
                try:
                    filename = batch_item.get("filename", "exported_file")
                    encoding = batch_item.get("encoding", "utf-8")
                    data = batch_item.get("data")
                    if not data:
                        logger.warning(
                            f"[ArtifactUpload] Batch item {filename} has no data, skipping"
                        )
                        continue

                    if encoding == "base64":
                        file_content = b64.b64decode(data)
                    else:
                        file_content = data.encode("utf-8") if isinstance(data, str) else data

                    mime_type = detect_mime_type(filename)
                    category = get_category_from_mime(mime_type)
                    artifact_id = str(uuid.uuid4())

                    # Yield artifact_created event immediately
                    yield AgentArtifactCreatedEvent(
                        artifact_id=artifact_id,
                        filename=filename,
                        mime_type=mime_type,
                        category=category.value,
                        size_bytes=len(file_content),
                        url=None,
                        preview_url=None,
                        tool_execution_id=tool_execution_id,
                        source_tool=tool_name,
                        source_path=batch_item.get("path"),
                    )

                    # Emit artifact_open for canvas-displayable content
                    canvas_type = get_canvas_content_type(mime_type, filename)
                    if canvas_type and len(file_content) < 500_000:
                        try:
                            text_content = file_content.decode("utf-8")
                            yield AgentArtifactOpenEvent(
                                artifact_id=artifact_id,
                                title=filename,
                                content=text_content,
                                content_type=canvas_type,
                                language=get_language_from_filename(filename),
                            )
                        except (UnicodeDecodeError, ValueError):
                            pass  # Binary content, skip canvas open

                    # Schedule background upload via ArtifactService.
                    logger.warning(
                        f"[ArtifactUpload] Scheduling batch upload: filename={filename}, "
                        f"size={len(file_content)}, project_id={project_id}"
                    )
                    _schedule_artifact_upload(
                        artifact_service=self._artifact_service,
                        file_content=file_content,
                        filename=filename,
                        project_id=project_id,
                        tenant_id=tenant_id,
                        tool_execution_id=tool_execution_id or "",
                        conversation_id=conversation_id or "",
                        tool_name=tool_name,
                        artifact_id=artifact_id,
                        source_path=batch_item.get("path"),
                        sandbox_id=sandbox_id,
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to process batch artifact {batch_item.get('filename', '?')}: {e}"
                    )
            return
        # Check for MCP content array with images/resources
        content = result.get("content", [])
        if not content:
            return

        # Check if there are any image or resource types
        has_rich_content = any(
            item.get("type") in ("image", "resource") for item in content if isinstance(item, dict)
        )
        if not has_rich_content:
            return

        try:
            # Extract artifacts from MCP result
            artifact_data_list = extract_artifacts_from_mcp_result(result, tool_name)

            for artifact_data in artifact_data_list:
                try:
                    # Upload artifact
                    artifact = await self._artifact_service.create_artifact(
                        file_content=artifact_data["content"],
                        filename=artifact_data["filename"],
                        project_id=project_id,
                        tenant_id=tenant_id,
                        sandbox_id=sandbox_id,
                        tool_execution_id=tool_execution_id,
                        conversation_id=conversation_id,
                        source_tool=tool_name,
                        source_path=artifact_data.get("source_path"),
                        metadata={
                            "extracted_from": "mcp_result",
                            "original_mime": artifact_data["mime_type"],
                        },
                    )

                    logger.info(
                        f"Created artifact {artifact.id} from tool {tool_name}: "
                        f"{artifact.filename} ({artifact.category.value}, "
                        f"{artifact.size_bytes} bytes)"
                    )

                    # Emit artifact created event
                    yield AgentArtifactCreatedEvent(
                        artifact_id=artifact.id,
                        filename=artifact.filename,
                        mime_type=artifact.mime_type,
                        category=artifact.category.value,
                        size_bytes=artifact.size_bytes,
                        url=artifact.url,
                        preview_url=artifact.preview_url,
                        tool_execution_id=tool_execution_id,
                        source_tool=tool_name,
                    )
                    # Emit artifact_open for canvas-displayable content
                    canvas_type = get_canvas_content_type(artifact.mime_type, artifact.filename)
                    if canvas_type and artifact.size_bytes < 500_000:
                        try:
                            text_content = artifact_data["content"].decode("utf-8")
                            yield AgentArtifactOpenEvent(
                                artifact_id=artifact.id,
                                title=artifact.filename,
                                content=text_content,
                                content_type=canvas_type,
                                language=get_language_from_filename(artifact.filename),
                            )
                        except (UnicodeDecodeError, ValueError):
                            pass  # Binary content, skip canvas open

                except Exception as e:
                    logger.error(f"Failed to create artifact from {tool_name}: {e}")

        except Exception as e:
            logger.error(f"Error processing artifacts from tool {tool_name}: {e}")


# -----------------------------------------------------------------------
# Background upload helper
# -----------------------------------------------------------------------


def _schedule_artifact_upload(
    *,
    artifact_service: ArtifactService,
    file_content: bytes,
    filename: str,
    project_id: str,
    tenant_id: str,
    tool_execution_id: str,
    conversation_id: str,
    tool_name: str,
    artifact_id: str,
    source_path: str | None = None,
    sandbox_id: str | None = None,
) -> None:
    """Schedule a background upload task via ArtifactService, preventing GC."""

    async def _do_upload() -> None:
        try:
            await artifact_service.create_artifact(
                file_content=file_content,
                filename=filename,
                project_id=project_id,
                tenant_id=tenant_id,
                sandbox_id=sandbox_id,
                tool_execution_id=tool_execution_id,
                conversation_id=conversation_id,
                source_tool=tool_name,
                source_path=source_path,
                metadata={"upload_source": "artifact_handler"},
            )
        except Exception as e:
            logger.error(f"[ArtifactUpload] Background upload failed: {filename}: {e}")

    task = asyncio.create_task(_do_upload())
    _artifact_bg_tasks.add(task)
    task.add_done_callback(_artifact_bg_tasks.discard)
