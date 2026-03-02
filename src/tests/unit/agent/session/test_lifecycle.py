"""Unit tests for SessionLifecycleManager and components."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.domain.model.agent.conversation.conversation import (
    Conversation,
    ConversationStatus,
)
from src.domain.model.agent.conversation.message import Message, MessageRole
from src.infrastructure.agent.session.lifecycle import (
    ArchiveResult,
    GCResult,
    LifecycleResult,
    SessionArchiver,
    SessionGarbageCollector,
    SessionLifecycleConfig,
    SessionLifecycleManager,
    SessionTrimmer,
    TrimResult,
)


def _make_conversation(
    *,
    conversation_id: str = "conv-1",
    project_id: str = "proj-1",
    status: ConversationStatus = ConversationStatus.ACTIVE,
    updated_at: datetime | None = None,
) -> Conversation:
    """Create a test conversation."""
    return Conversation(
        id=conversation_id,
        project_id=project_id,
        tenant_id="tenant-1",
        user_id="user-1",
        title="Test Conversation",
        status=status,
        updated_at=updated_at,
        created_at=datetime.now(UTC) - timedelta(hours=48),
    )


def _make_message(
    *,
    message_id: str = "msg-1",
    conversation_id: str = "conv-1",
    role: MessageRole = MessageRole.USER,
    content: str = "Hello world",
) -> Message:
    """Create a test message."""
    return Message(
        id=message_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at=datetime.now(UTC),
    )


def _make_messages(count: int, conversation_id: str = "conv-1") -> list[Message]:
    """Create a list of test messages with sequential IDs and timestamps."""
    base_time = datetime.now(UTC) - timedelta(hours=count)
    messages: list[Message] = []
    for i in range(count):
        role = MessageRole.SYSTEM if i == 0 else MessageRole.USER
        messages.append(
            Message(
                id=f"msg-{i}",
                conversation_id=conversation_id,
                role=role,
                content=f"Message content {i}",
                created_at=base_time + timedelta(minutes=i),
            )
        )
    return messages


@pytest.mark.unit
class TestSessionLifecycleConfig:
    """Tests for SessionLifecycleConfig defaults."""

    def test_defaults(self) -> None:
        config = SessionLifecycleConfig()
        assert config.max_messages_per_session == 100
        assert config.trim_keep_count == 50
        assert config.max_token_budget == 128_000
        assert config.inactivity_threshold_hours == 24
        assert config.session_ttl_hours == 168
        assert config.archive_batch_size == 50
        assert config.gc_batch_size == 50

    def test_custom_values(self) -> None:
        config = SessionLifecycleConfig(
            max_messages_per_session=200,
            trim_keep_count=80,
        )
        assert config.max_messages_per_session == 200
        assert config.trim_keep_count == 80


@pytest.mark.unit
class TestResultDataclasses:
    """Tests for frozen result dataclasses."""

    def test_trim_result_is_frozen(self) -> None:
        result = TrimResult(
            conversation_id="c1",
            messages_before=100,
            messages_after=50,
            tokens_freed=5000,
            trimmed=True,
        )
        assert result.trimmed is True
        with pytest.raises(AttributeError):
            result.trimmed = False  # type: ignore[misc]

    def test_archive_result_defaults(self) -> None:
        result = ArchiveResult(archived_count=2, skipped_count=3)
        assert result.failed_ids == []

    def test_gc_result_defaults(self) -> None:
        result = GCResult(deleted_count=1, skipped_count=0)
        assert result.failed_ids == []

    def test_lifecycle_result_defaults(self) -> None:
        result = LifecycleResult()
        assert result.trim_results == []
        assert result.archive_result is None
        assert result.gc_result is None


@pytest.mark.unit
class TestSessionTrimmer:
    """Tests for SessionTrimmer."""

    async def test_no_trim_when_under_limit(self) -> None:
        """Should return untrimmed result when messages are within limits."""
        config = SessionLifecycleConfig(max_messages_per_session=100)
        message_repo = AsyncMock()
        messages = _make_messages(50)
        message_repo.list_by_conversation = AsyncMock(return_value=messages)

        trimmer = SessionTrimmer(message_repo=message_repo, config=config)
        conversation = _make_conversation()

        result = await trimmer.trim(conversation)

        assert result.trimmed is False
        assert result.messages_before == 50
        assert result.messages_after == 50
        assert result.tokens_freed == 0
        message_repo.delete_by_conversation.assert_not_called()

    async def test_trim_when_over_limit(self) -> None:
        """Should trim messages when over the max limit."""
        config = SessionLifecycleConfig(
            max_messages_per_session=10,
            trim_keep_count=5,
            max_token_budget=1_000_000,
        )
        message_repo = AsyncMock()
        messages = _make_messages(20)
        message_repo.list_by_conversation = AsyncMock(return_value=messages)

        trimmer = SessionTrimmer(message_repo=message_repo, config=config)
        conversation = _make_conversation()

        result = await trimmer.trim(conversation)

        assert result.trimmed is True
        assert result.messages_before == 20
        assert result.messages_after < 20
        message_repo.delete_by_conversation.assert_awaited_once_with("conv-1")

    async def test_system_prompt_preserved(self) -> None:
        """Should keep the first system message when trimming."""
        config = SessionLifecycleConfig(
            max_messages_per_session=5,
            trim_keep_count=3,
            max_token_budget=1_000_000,
        )
        message_repo = AsyncMock()
        messages = _make_messages(10)
        message_repo.list_by_conversation = AsyncMock(return_value=messages)

        trimmer = SessionTrimmer(message_repo=message_repo, config=config)
        conversation = _make_conversation()

        result = await trimmer.trim(conversation)

        assert result.trimmed is True
        assert result.messages_after == 4
        assert result.messages_after == 4

    async def test_empty_messages(self) -> None:
        """Should handle empty message list gracefully."""
        config = SessionLifecycleConfig(max_messages_per_session=100)
        message_repo = AsyncMock()
        message_repo.list_by_conversation = AsyncMock(return_value=[])

        trimmer = SessionTrimmer(message_repo=message_repo, config=config)
        conversation = _make_conversation()

        result = await trimmer.trim(conversation)

        assert result.trimmed is False
        assert result.messages_before == 0
        assert result.messages_after == 0

    async def test_token_budget_enforcement(self) -> None:
        """Should respect token budget when keeping messages."""
        config = SessionLifecycleConfig(
            max_messages_per_session=5,
            trim_keep_count=50,
            max_token_budget=10,
        )
        message_repo = AsyncMock()
        messages = [
            _make_message(
                message_id=f"msg-{i}",
                role=MessageRole.SYSTEM if i == 0 else MessageRole.USER,
                content="x" * 200,
            )
            for i in range(10)
        ]
        base_time = datetime.now(UTC) - timedelta(hours=10)
        for i, msg in enumerate(messages):
            msg.created_at = base_time + timedelta(minutes=i)
        message_repo.list_by_conversation = AsyncMock(return_value=messages)

        trimmer = SessionTrimmer(message_repo=message_repo, config=config)
        conversation = _make_conversation()

        result = await trimmer.trim(conversation)

        assert result.trimmed is True
        assert result.messages_after >= 1

    async def test_tokens_freed_estimation(self) -> None:
        """Should estimate freed tokens correctly."""
        config = SessionLifecycleConfig(
            max_messages_per_session=5,
            trim_keep_count=3,
            max_token_budget=1_000_000,
        )
        message_repo = AsyncMock()
        messages = _make_messages(10)
        message_repo.list_by_conversation = AsyncMock(return_value=messages)

        trimmer = SessionTrimmer(message_repo=message_repo, config=config)
        conversation = _make_conversation()

        result = await trimmer.trim(conversation)

        assert result.tokens_freed > 0

    async def test_no_system_messages(self) -> None:
        """Should handle conversations with no system messages."""
        config = SessionLifecycleConfig(
            max_messages_per_session=5,
            trim_keep_count=3,
            max_token_budget=1_000_000,
        )
        message_repo = AsyncMock()
        base_time = datetime.now(UTC) - timedelta(hours=10)
        messages = [
            Message(
                id=f"msg-{i}",
                conversation_id="conv-1",
                role=MessageRole.USER,
                content=f"Content {i}",
                created_at=base_time + timedelta(minutes=i),
            )
            for i in range(10)
        ]
        message_repo.list_by_conversation = AsyncMock(return_value=messages)

        trimmer = SessionTrimmer(message_repo=message_repo, config=config)
        conversation = _make_conversation()

        result = await trimmer.trim(conversation)

        assert result.trimmed is True
        assert result.messages_after == 3



@pytest.mark.unit
class TestSessionArchiver:
    """Tests for SessionArchiver."""

    async def test_archive_inactive_conversations(self) -> None:
        """Should archive conversations past the inactivity threshold."""
        config = SessionLifecycleConfig(inactivity_threshold_hours=24)
        conversation_repo = AsyncMock()
        old_conversation = _make_conversation(
            updated_at=datetime.now(UTC) - timedelta(hours=48),
        )
        conversation_repo.list_by_project = AsyncMock(
            return_value=[old_conversation],
        )

        archiver = SessionArchiver(
            conversation_repo=conversation_repo,
            config=config,
        )

        result = await archiver.archive_inactive("proj-1")

        assert result.archived_count == 1
        assert result.skipped_count == 0
        assert result.failed_ids == []
        assert old_conversation.status == ConversationStatus.ARCHIVED
        conversation_repo.save.assert_awaited_once_with(old_conversation)

    async def test_skip_recent_conversations(self) -> None:
        """Should skip conversations that were recently active."""
        config = SessionLifecycleConfig(inactivity_threshold_hours=24)
        conversation_repo = AsyncMock()
        recent_conversation = _make_conversation(
            updated_at=datetime.now(UTC) - timedelta(hours=1),
        )
        conversation_repo.list_by_project = AsyncMock(
            return_value=[recent_conversation],
        )

        archiver = SessionArchiver(
            conversation_repo=conversation_repo,
            config=config,
        )

        result = await archiver.archive_inactive("proj-1")

        assert result.archived_count == 0
        assert result.skipped_count == 1
        assert recent_conversation.status == ConversationStatus.ACTIVE
        conversation_repo.save.assert_not_called()

    async def test_mixed_conversations(self) -> None:
        """Should archive old and skip recent conversations in same batch."""
        config = SessionLifecycleConfig(inactivity_threshold_hours=24)
        conversation_repo = AsyncMock()
        old = _make_conversation(
            conversation_id="old-1",
            updated_at=datetime.now(UTC) - timedelta(hours=48),
        )
        recent = _make_conversation(
            conversation_id="recent-1",
            updated_at=datetime.now(UTC) - timedelta(hours=1),
        )
        conversation_repo.list_by_project = AsyncMock(return_value=[old, recent])

        archiver = SessionArchiver(
            conversation_repo=conversation_repo,
            config=config,
        )

        result = await archiver.archive_inactive("proj-1")

        assert result.archived_count == 1
        assert result.skipped_count == 1

    async def test_archive_failure_handling(self) -> None:
        """Should capture failed conversation IDs without stopping."""
        config = SessionLifecycleConfig(inactivity_threshold_hours=24)
        conversation_repo = AsyncMock()
        failing_conversation = _make_conversation(
            updated_at=datetime.now(UTC) - timedelta(hours=48),
        )
        conversation_repo.list_by_project = AsyncMock(
            return_value=[failing_conversation],
        )
        conversation_repo.save = AsyncMock(side_effect=RuntimeError("DB error"))

        archiver = SessionArchiver(
            conversation_repo=conversation_repo,
            config=config,
        )

        result = await archiver.archive_inactive("proj-1")

        assert result.archived_count == 0
        assert result.failed_ids == ["conv-1"]

    async def test_empty_project(self) -> None:
        """Should handle project with no active conversations."""
        config = SessionLifecycleConfig()
        conversation_repo = AsyncMock()
        conversation_repo.list_by_project = AsyncMock(return_value=[])

        archiver = SessionArchiver(
            conversation_repo=conversation_repo,
            config=config,
        )

        result = await archiver.archive_inactive("proj-1")

        assert result.archived_count == 0
        assert result.skipped_count == 0

    async def test_uses_created_at_fallback(self) -> None:
        """Should use created_at when updated_at is None."""
        config = SessionLifecycleConfig(inactivity_threshold_hours=24)
        conversation_repo = AsyncMock()
        conversation = _make_conversation(updated_at=None)
        conversation_repo.list_by_project = AsyncMock(return_value=[conversation])

        archiver = SessionArchiver(
            conversation_repo=conversation_repo,
            config=config,
        )

        result = await archiver.archive_inactive("proj-1")

        assert result.archived_count == 1



@pytest.mark.unit
class TestSessionGarbageCollector:
    """Tests for SessionGarbageCollector."""

    async def test_gc_expired_archived_conversations(self) -> None:
        """Should delete archived conversations past TTL."""
        config = SessionLifecycleConfig(session_ttl_hours=168)
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()
        expired = _make_conversation(
            status=ConversationStatus.ARCHIVED,
            updated_at=datetime.now(UTC) - timedelta(hours=200),
        )
        conversation_repo.list_by_project = AsyncMock(return_value=[expired])

        gc = SessionGarbageCollector(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            config=config,
        )

        result = await gc.collect("proj-1")

        assert result.deleted_count == 1
        assert result.skipped_count == 0
        assert expired.status == ConversationStatus.DELETED
        message_repo.delete_by_conversation.assert_awaited_once_with("conv-1")
        conversation_repo.save.assert_awaited_once_with(expired)

    async def test_skip_recent_archived(self) -> None:
        """Should skip archived conversations not yet past TTL."""
        config = SessionLifecycleConfig(session_ttl_hours=168)
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()
        recent_archived = _make_conversation(
            status=ConversationStatus.ARCHIVED,
            updated_at=datetime.now(UTC) - timedelta(hours=24),
        )
        conversation_repo.list_by_project = AsyncMock(
            return_value=[recent_archived],
        )

        gc = SessionGarbageCollector(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            config=config,
        )

        result = await gc.collect("proj-1")

        assert result.deleted_count == 0
        assert result.skipped_count == 1
        assert recent_archived.status == ConversationStatus.ARCHIVED
        message_repo.delete_by_conversation.assert_not_called()

    async def test_gc_failure_handling(self) -> None:
        """Should capture failed IDs without stopping."""
        config = SessionLifecycleConfig(session_ttl_hours=168)
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()
        message_repo.delete_by_conversation = AsyncMock(
            side_effect=RuntimeError("DB error"),
        )
        expired = _make_conversation(
            status=ConversationStatus.ARCHIVED,
            updated_at=datetime.now(UTC) - timedelta(hours=200),
        )
        conversation_repo.list_by_project = AsyncMock(return_value=[expired])

        gc = SessionGarbageCollector(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            config=config,
        )

        result = await gc.collect("proj-1")

        assert result.deleted_count == 0
        assert result.failed_ids == ["conv-1"]

    async def test_gc_empty_project(self) -> None:
        """Should handle project with no archived conversations."""
        config = SessionLifecycleConfig()
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()
        conversation_repo.list_by_project = AsyncMock(return_value=[])

        gc = SessionGarbageCollector(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            config=config,
        )

        result = await gc.collect("proj-1")

        assert result.deleted_count == 0
        assert result.skipped_count == 0

    async def test_gc_deletes_messages_before_conversation(self) -> None:
        """Should delete messages before marking conversation as deleted."""
        config = SessionLifecycleConfig(session_ttl_hours=168)
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()

        call_order: list[str] = []
        def _track_delete(_conv_id: str) -> None:
            call_order.append("delete_messages")

        message_repo.delete_by_conversation = AsyncMock(
            side_effect=_track_delete,
        )

        def _track_save(_conv: object) -> None:
            call_order.append("save_conversation")

        conversation_repo.save = AsyncMock(
            side_effect=_track_save,
        )

        expired = _make_conversation(
            status=ConversationStatus.ARCHIVED,
            updated_at=datetime.now(UTC) - timedelta(hours=200),
        )
        conversation_repo.list_by_project = AsyncMock(return_value=[expired])

        gc = SessionGarbageCollector(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            config=config,
        )

        _ = await gc.collect("proj-1")

        assert call_order == ["delete_messages", "save_conversation"]



@pytest.mark.unit
class TestSessionLifecycleManager:
    """Tests for SessionLifecycleManager orchestration."""

    async def test_run_lifecycle_full_pipeline(self) -> None:
        """Should run trim, archive, and GC in order."""
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()
        config = SessionLifecycleConfig(
            max_messages_per_session=100,
            inactivity_threshold_hours=24,
            session_ttl_hours=168,
        )

        conversation_repo.list_by_project = AsyncMock(return_value=[])

        manager = SessionLifecycleManager(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            config=config,
        )

        result = await manager.run_lifecycle("proj-1")

        assert isinstance(result, LifecycleResult)
        assert result.trim_results == []
        assert result.archive_result is not None
        assert result.gc_result is not None

    async def test_default_config(self) -> None:
        """Should use default config when none provided."""
        manager = SessionLifecycleManager(
            conversation_repo=AsyncMock(),
            message_repo=AsyncMock(),
        )

        assert isinstance(manager.trimmer, SessionTrimmer)

    async def test_property_access(self) -> None:
        """Should expose trimmer, archiver, and gc via properties."""
        manager = SessionLifecycleManager(
            conversation_repo=AsyncMock(),
            message_repo=AsyncMock(),
        )

        assert isinstance(manager.trimmer, SessionTrimmer)
        assert isinstance(manager.archiver, SessionArchiver)
        assert isinstance(manager.gc, SessionGarbageCollector)

    async def test_lifecycle_order(self) -> None:
        """Should execute trim -> archive -> GC in sequence."""
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()

        call_order: list[str] = []


        async def tracking_list(**kwargs: object) -> list[object]:
            status = kwargs.get("status")
            if status == ConversationStatus.ACTIVE:
                if "trim" not in call_order:
                    call_order.append("trim")
                else:
                    call_order.append("archive")
            elif status == ConversationStatus.ARCHIVED:
                call_order.append("gc")
            return []

        conversation_repo.list_by_project = tracking_list

        manager = SessionLifecycleManager(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
        )

        _ = await manager.run_lifecycle("proj-1")

        assert call_order == ["trim", "archive", "gc"]

    async def test_trimming_with_active_conversations(self) -> None:
        """Should trim active conversations that exceed limits."""
        config = SessionLifecycleConfig(
            max_messages_per_session=5,
            trim_keep_count=3,
            max_token_budget=1_000_000,
        )
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()

        active_conv = _make_conversation(
            updated_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        messages = _make_messages(10)

        call_count = 0

        async def mock_list_by_project(**kwargs: object) -> list[Conversation]:
            nonlocal call_count
            call_count += 1
            status = kwargs.get("status")
            if status == ConversationStatus.ACTIVE:
                return [active_conv]
            return []

        conversation_repo.list_by_project = mock_list_by_project
        message_repo.list_by_conversation = AsyncMock(return_value=messages)

        manager = SessionLifecycleManager(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            config=config,
        )

        result = await manager.run_lifecycle("proj-1")

        assert len(result.trim_results) == 1
        assert result.trim_results[0].trimmed is True

    async def test_trimming_failure_does_not_block_pipeline(self) -> None:
        """Should continue archive/GC even if trimming fails for a conversation."""
        config = SessionLifecycleConfig(max_messages_per_session=5)
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()

        active_conv = _make_conversation(
            updated_at=datetime.now(UTC) - timedelta(minutes=5),
        )

        async def mock_list_by_project(**kwargs: object) -> list[Conversation]:
            status = kwargs.get("status")
            if status == ConversationStatus.ACTIVE:
                return [active_conv]
            return []

        conversation_repo.list_by_project = mock_list_by_project
        message_repo.list_by_conversation = AsyncMock(
            side_effect=RuntimeError("DB error"),
        )

        manager = SessionLifecycleManager(
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            config=config,
        )

        result = await manager.run_lifecycle("proj-1")

        assert result.trim_results == []
        assert result.archive_result is not None
        assert result.gc_result is not None
