"""Tests for Phase 3 Wave 3: Conversation fork/merge entity extensions."""

from __future__ import annotations

import json

import pytest

from src.domain.model.agent.conversation.conversation import Conversation, ConversationStatus
from src.domain.model.agent.merge_strategy import MergeStrategy


def _make_conversation(**overrides: object) -> Conversation:
    """Create a minimal Conversation for testing."""
    defaults: dict[str, object] = {
        "project_id": "proj-1",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "title": "Test conversation",
    }
    defaults.update(overrides)
    return Conversation(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fork/merge field defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConversationForkFieldDefaults:
    """New fork/merge fields must have correct defaults."""

    def test_fork_source_id_defaults_to_none(self) -> None:
        conv = _make_conversation()
        assert conv.fork_source_id is None

    def test_fork_context_snapshot_defaults_to_none(self) -> None:
        conv = _make_conversation()
        assert conv.fork_context_snapshot is None

    def test_merge_strategy_defaults_to_result_only(self) -> None:
        conv = _make_conversation()
        assert conv.merge_strategy == MergeStrategy.RESULT_ONLY

    def test_fork_fields_are_settable_at_construction(self) -> None:
        conv = _make_conversation(
            fork_source_id="parent-conv-1",
            fork_context_snapshot='{"summary": "context"}',
            merge_strategy=MergeStrategy.FULL_HISTORY,
        )
        assert conv.fork_source_id == "parent-conv-1"
        assert conv.fork_context_snapshot == '{"summary": "context"}'
        assert conv.merge_strategy == MergeStrategy.FULL_HISTORY


# ---------------------------------------------------------------------------
# is_forked property
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConversationIsForked:
    """The is_forked property signals whether this conversation was forked."""

    def test_is_forked_false_when_no_fork_source(self) -> None:
        conv = _make_conversation()
        assert conv.is_forked is False

    def test_is_forked_true_when_fork_source_set(self) -> None:
        conv = _make_conversation(fork_source_id="parent-conv-1")
        assert conv.is_forked is True


# ---------------------------------------------------------------------------
# fork() class method
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConversationFork:
    """Conversation.fork() creates a child conversation from a parent."""

    def test_fork_creates_new_conversation(self) -> None:
        parent = _make_conversation(id="parent-1")
        child = parent.fork(
            user_id="user-1",
            title="SubAgent session",
        )
        assert isinstance(child, Conversation)
        assert child.id != parent.id

    def test_fork_sets_fork_source_id(self) -> None:
        parent = _make_conversation(id="parent-1")
        child = parent.fork(user_id="user-1", title="child")
        assert child.fork_source_id == "parent-1"

    def test_fork_sets_parent_conversation_id(self) -> None:
        parent = _make_conversation(id="parent-1")
        child = parent.fork(user_id="user-1", title="child")
        assert child.parent_conversation_id == "parent-1"

    def test_fork_inherits_project_and_tenant(self) -> None:
        parent = _make_conversation(project_id="proj-x", tenant_id="tenant-x")
        child = parent.fork(user_id="user-1", title="child")
        assert child.project_id == "proj-x"
        assert child.tenant_id == "tenant-x"

    def test_fork_default_merge_strategy(self) -> None:
        parent = _make_conversation()
        child = parent.fork(user_id="user-1", title="child")
        assert child.merge_strategy == MergeStrategy.RESULT_ONLY

    def test_fork_custom_merge_strategy(self) -> None:
        parent = _make_conversation()
        child = parent.fork(
            user_id="user-1",
            title="child",
            merge_strategy=MergeStrategy.SUMMARY,
        )
        assert child.merge_strategy == MergeStrategy.SUMMARY

    def test_fork_with_context_snapshot(self) -> None:
        parent = _make_conversation()
        snapshot = json.dumps({"messages": ["hello"]})
        child = parent.fork(
            user_id="user-1",
            title="child",
            context_snapshot=snapshot,
        )
        assert child.fork_context_snapshot == snapshot

    def test_fork_starts_active(self) -> None:
        parent = _make_conversation()
        child = parent.fork(user_id="user-1", title="child")
        assert child.status == ConversationStatus.ACTIVE

    def test_fork_has_zero_message_count(self) -> None:
        parent = _make_conversation(message_count=42)
        child = parent.fork(user_id="user-1", title="child")
        assert child.message_count == 0


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip with fork fields
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConversationForkSerialization:
    """to_dict/from_dict must include fork/merge fields."""

    def test_to_dict_includes_fork_source_id(self) -> None:
        conv = _make_conversation(fork_source_id="p-1")
        d = conv.to_dict()
        assert d["fork_source_id"] == "p-1"

    def test_to_dict_includes_merge_strategy(self) -> None:
        conv = _make_conversation(merge_strategy=MergeStrategy.FULL_HISTORY)
        d = conv.to_dict()
        assert d["merge_strategy"] == "full_history"

    def test_to_dict_includes_fork_context_snapshot(self) -> None:
        conv = _make_conversation(fork_context_snapshot="snap")
        d = conv.to_dict()
        assert d["fork_context_snapshot"] == "snap"

    def test_from_dict_restores_fork_fields(self) -> None:
        conv = _make_conversation(
            fork_source_id="p-1",
            fork_context_snapshot="snap",
            merge_strategy=MergeStrategy.SUMMARY,
        )
        d = conv.to_dict()
        restored = Conversation.from_dict(d)
        assert restored.fork_source_id == "p-1"
        assert restored.fork_context_snapshot == "snap"
        assert restored.merge_strategy == MergeStrategy.SUMMARY

    def test_from_dict_defaults_when_fork_fields_absent(self) -> None:
        """Backward compat: dicts without fork fields use defaults."""
        conv = _make_conversation()
        d = conv.to_dict()
        d.pop("fork_source_id", None)
        d.pop("fork_context_snapshot", None)
        d.pop("merge_strategy", None)
        restored = Conversation.from_dict(d)
        assert restored.fork_source_id is None
        assert restored.fork_context_snapshot is None
        assert restored.merge_strategy == MergeStrategy.RESULT_ONLY


# ---------------------------------------------------------------------------
# is_subagent_session interaction with fork
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConversationForkSubagentInteraction:
    """Fork sets parent_conversation_id, which triggers is_subagent_session."""

    def test_forked_conversation_is_subagent_session(self) -> None:
        parent = _make_conversation(id="parent-1")
        child = parent.fork(user_id="user-1", title="child")
        assert child.is_subagent_session is True

    def test_non_forked_conversation_is_not_subagent_session(self) -> None:
        conv = _make_conversation()
        assert conv.is_subagent_session is False
