"""Session Lifecycle Management - Trimming, archival, and garbage collection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.domain.model.agent.conversation.conversation import (
    Conversation,
    ConversationStatus,
)
from src.domain.model.agent.conversation.message import Message, MessageRole
from src.domain.ports.repositories.agent_repository import (
    ConversationRepository,
    MessageRepository,
)
from src.infrastructure.agent.context.compaction import estimate_tokens

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class SessionLifecycleConfig:
    """Configuration for session lifecycle management.

    Attributes:
        max_messages_per_session: Maximum messages before trimming kicks in.
        trim_keep_count: Number of recent messages to keep after trimming.
        max_token_budget: Maximum token budget per session.
        inactivity_threshold_hours: Hours of inactivity before archival.
        session_ttl_hours: Hours before expired sessions are garbage-collected.
        archive_batch_size: Number of sessions to archive per batch.
        gc_batch_size: Number of sessions to garbage-collect per batch.
    """

    max_messages_per_session: int = 100
    trim_keep_count: int = 50
    max_token_budget: int = 128_000
    inactivity_threshold_hours: int = 24
    session_ttl_hours: int = 168
    archive_batch_size: int = 50
    gc_batch_size: int = 50


@dataclass(kw_only=True, frozen=True)
class TrimResult:
    """Result of a session trimming operation.

    Attributes:
        conversation_id: ID of the trimmed conversation.
        messages_before: Message count before trimming.
        messages_after: Message count after trimming.
        tokens_freed: Estimated tokens freed by trimming.
        trimmed: Whether any messages were actually trimmed.
    """

    conversation_id: str
    messages_before: int
    messages_after: int
    tokens_freed: int
    trimmed: bool


@dataclass(kw_only=True, frozen=True)
class ArchiveResult:
    """Result of a session archival operation.

    Attributes:
        archived_count: Number of conversations archived.
        skipped_count: Number of conversations skipped.
        failed_ids: IDs of conversations that failed to archive.
    """

    archived_count: int
    skipped_count: int
    failed_ids: list[str] = field(default_factory=list)


@dataclass(kw_only=True, frozen=True)
class GCResult:
    """Result of a garbage collection operation.

    Attributes:
        deleted_count: Number of conversations deleted.
        skipped_count: Number of conversations skipped.
        failed_ids: IDs of conversations that failed to delete.
    """

    deleted_count: int
    skipped_count: int
    failed_ids: list[str] = field(default_factory=list)


@dataclass(kw_only=True, frozen=True)
class LifecycleResult:
    """Combined result of a full lifecycle run.

    Attributes:
        trim_results: Results from trimming operations.
        archive_result: Result from archival operation.
        gc_result: Result from garbage collection.
    """

    trim_results: list[TrimResult] = field(default_factory=list)
    archive_result: ArchiveResult | None = None
    gc_result: GCResult | None = None


class SessionTrimmer:
    """Trims old messages from conversations exceeding limits.

    Keeps the system prompt (first system message) and the N most recent
    messages, removing everything in between. Respects token budget.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        config: SessionLifecycleConfig,
    ) -> None:
        self._message_repo = message_repo
        self._config = config

    async def trim(self, conversation: Conversation) -> TrimResult:
        """Trim messages for a single conversation.

        Args:
            conversation: The conversation to trim.

        Returns:
            TrimResult describing what happened.
        """
        messages = await self._message_repo.list_by_conversation(
            conversation_id=conversation.id,
            limit=self._config.max_messages_per_session + 100,
        )

        messages_before = len(messages)

        if messages_before <= self._config.max_messages_per_session:
            return TrimResult(
                conversation_id=conversation.id,
                messages_before=messages_before,
                messages_after=messages_before,
                tokens_freed=0,
                trimmed=False,
            )

        keep_messages = self._select_messages_to_keep(messages)
        messages_after = len(keep_messages)

        tokens_freed = self._estimate_freed_tokens(messages, keep_messages)

        remove_ids = {m.id for m in messages} - {m.id for m in keep_messages}
        if remove_ids:
            await self._message_repo.delete_by_conversation(conversation.id)

        logger.info(
            "Trimmed conversation %s: %d -> %d messages, ~%d tokens freed",
            conversation.id,
            messages_before,
            messages_after,
            tokens_freed,
        )

        return TrimResult(
            conversation_id=conversation.id,
            messages_before=messages_before,
            messages_after=messages_after,
            tokens_freed=tokens_freed,
            trimmed=messages_before > messages_after,
        )

    def _select_messages_to_keep(self, messages: list[Message]) -> list[Message]:
        """Select which messages to keep after trimming.

        Strategy: Keep the first system message (system prompt) and
        the N most recent messages, where N is trim_keep_count.

        Args:
            messages: All messages in chronological order.

        Returns:
            List of messages to keep.
        """
        if not messages:
            return []

        keep: list[Message] = []

        system_messages = [m for m in messages if m.role == MessageRole.SYSTEM]
        if system_messages:
            keep.append(system_messages[0])

        recent = messages[-self._config.trim_keep_count :]

        keep_ids = {m.id for m in keep}
        for msg in recent:
            if msg.id not in keep_ids:
                keep.append(msg)
                keep_ids.add(msg.id)

        keep.sort(key=lambda m: m.created_at)

        total_tokens = 0
        budget_kept: list[Message] = []
        for msg in keep:
            msg_tokens = estimate_tokens(msg.content)
            if total_tokens + msg_tokens <= self._config.max_token_budget:
                budget_kept.append(msg)
                total_tokens += msg_tokens
            else:
                if msg.role == MessageRole.SYSTEM and not budget_kept:
                    budget_kept.append(msg)
                    total_tokens += msg_tokens

        return budget_kept if budget_kept else keep

    def _estimate_freed_tokens(
        self,
        all_messages: list[Message],
        kept_messages: list[Message],
    ) -> int:
        """Estimate tokens freed by trimming.

        Args:
            all_messages: Original message list.
            kept_messages: Messages that will be kept.

        Returns:
            Estimated freed token count.
        """
        kept_ids = {m.id for m in kept_messages}
        freed = 0
        for msg in all_messages:
            if msg.id not in kept_ids:
                freed += estimate_tokens(msg.content)
        return freed


class SessionArchiver:
    """Archives inactive sessions.

    Identifies conversations that have been inactive beyond the configured
    threshold and marks them as archived.
    """

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        config: SessionLifecycleConfig,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._config = config

    async def archive_inactive(self, project_id: str) -> ArchiveResult:
        """Archive inactive conversations for a project.

        Args:
            project_id: The project to scan for inactive conversations.

        Returns:
            ArchiveResult describing what happened.
        """
        cutoff = datetime.now(UTC) - timedelta(
            hours=self._config.inactivity_threshold_hours,
        )

        active_conversations = await self._conversation_repo.list_by_project(
            project_id=project_id,
            status=ConversationStatus.ACTIVE,
            limit=self._config.archive_batch_size,
        )

        archived_count = 0
        skipped_count = 0
        failed_ids: list[str] = []

        for conversation in active_conversations:
            last_activity = conversation.updated_at or conversation.created_at
            if last_activity >= cutoff:
                skipped_count += 1
                continue

            try:
                conversation.archive()
                await self._conversation_repo.save(conversation)
                archived_count += 1
                logger.info(
                    "Archived conversation %s (last activity: %s)",
                    conversation.id,
                    last_activity.isoformat(),
                )
            except Exception:
                logger.exception(
                    "Failed to archive conversation %s",
                    conversation.id,
                )
                failed_ids.append(conversation.id)

        logger.info(
            "Archive run for project %s: archived=%d, skipped=%d, failed=%d",
            project_id,
            archived_count,
            skipped_count,
            len(failed_ids),
        )

        return ArchiveResult(
            archived_count=archived_count,
            skipped_count=skipped_count,
            failed_ids=failed_ids,
        )


class SessionGarbageCollector:
    """Removes expired archived sessions.

    Only deletes sessions that have already been archived and whose
    TTL has expired. Never hard-deletes active sessions.
    """

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        config: SessionLifecycleConfig,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._config = config

    async def collect(self, project_id: str) -> GCResult:
        """Run garbage collection for a project.

        Only targets ARCHIVED conversations past their TTL.

        Args:
            project_id: The project to garbage-collect.

        Returns:
            GCResult describing what happened.
        """
        ttl_cutoff = datetime.now(UTC) - timedelta(
            hours=self._config.session_ttl_hours,
        )

        archived_conversations = await self._conversation_repo.list_by_project(
            project_id=project_id,
            status=ConversationStatus.ARCHIVED,
            limit=self._config.gc_batch_size,
        )

        deleted_count = 0
        skipped_count = 0
        failed_ids: list[str] = []

        for conversation in archived_conversations:
            last_activity = conversation.updated_at or conversation.created_at
            if last_activity >= ttl_cutoff:
                skipped_count += 1
                continue

            try:
                await self._message_repo.delete_by_conversation(conversation.id)
                conversation.delete()
                await self._conversation_repo.save(conversation)
                deleted_count += 1
                logger.info(
                    "Garbage-collected conversation %s (archived at: %s)",
                    conversation.id,
                    last_activity.isoformat(),
                )
            except Exception:
                logger.exception(
                    "Failed to garbage-collect conversation %s",
                    conversation.id,
                )
                failed_ids.append(conversation.id)

        logger.info(
            "GC run for project %s: deleted=%d, skipped=%d, failed=%d",
            project_id,
            deleted_count,
            skipped_count,
            len(failed_ids),
        )

        return GCResult(
            deleted_count=deleted_count,
            skipped_count=skipped_count,
            failed_ids=failed_ids,
        )


class SessionLifecycleManager:
    """Orchestrates all session lifecycle operations.

    Coordinates trimming, archival, and garbage collection in the
    correct order: trim first, then archive, then GC.
    """

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        config: SessionLifecycleConfig | None = None,
    ) -> None:
        self._config = config or SessionLifecycleConfig()
        self._trimmer = SessionTrimmer(
            message_repo=message_repo,
            config=self._config,
        )
        self._archiver = SessionArchiver(
            conversation_repo=conversation_repo,
            config=self._config,
        )
        self._gc = SessionGarbageCollector(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            config=self._config,
        )
        self._conversation_repo = conversation_repo

    @property
    def trimmer(self) -> SessionTrimmer:
        """Access the session trimmer."""
        return self._trimmer

    @property
    def archiver(self) -> SessionArchiver:
        """Access the session archiver."""
        return self._archiver

    @property
    def gc(self) -> SessionGarbageCollector:
        """Access the garbage collector."""
        return self._gc

    async def run_lifecycle(self, project_id: str) -> LifecycleResult:
        """Run the full lifecycle management pipeline for a project.

        Execution order:
        1. Trim active conversations that exceed message limits
        2. Archive inactive conversations
        3. Garbage-collect expired archived conversations

        Args:
            project_id: The project to manage.

        Returns:
            LifecycleResult with results from all phases.
        """
        logger.info("Starting lifecycle run for project %s", project_id)

        trim_results = await self._run_trimming(project_id)

        archive_result = await self._archiver.archive_inactive(project_id)

        gc_result = await self._gc.collect(project_id)

        logger.info(
            "Lifecycle run complete for project %s: trimmed=%d, archived=%d, gc_deleted=%d",
            project_id,
            len([r for r in trim_results if r.trimmed]),
            archive_result.archived_count,
            gc_result.deleted_count,
        )

        return LifecycleResult(
            trim_results=trim_results,
            archive_result=archive_result,
            gc_result=gc_result,
        )

    async def _run_trimming(self, project_id: str) -> list[TrimResult]:
        """Run trimming on all active conversations in a project.

        Args:
            project_id: The project to trim.

        Returns:
            List of TrimResult for each conversation processed.
        """
        active_conversations = await self._conversation_repo.list_by_project(
            project_id=project_id,
            status=ConversationStatus.ACTIVE,
            limit=self._config.archive_batch_size,
        )

        results: list[TrimResult] = []
        for conversation in active_conversations:
            try:
                result = await self._trimmer.trim(conversation)
                results.append(result)
            except Exception:
                logger.exception(
                    "Failed to trim conversation %s",
                    conversation.id,
                )

        return results
