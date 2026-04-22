"""Tests for workspace-level HITL default blocking categories (Phase-5 G5)."""

from __future__ import annotations

import pytest

from src.application.services.agent.workspace_hitl_defaults import merge_blocking_categories


@pytest.mark.unit
class TestMergeBlockingCategories:
    def test_both_none_returns_empty(self) -> None:
        assert merge_blocking_categories(
            workspace_defaults=None, conversation_overrides=None
        ) == frozenset()

    def test_workspace_only(self) -> None:
        out = merge_blocking_categories(
            workspace_defaults=["payment", "delete_project"],
            conversation_overrides=None,
        )
        assert out == frozenset({"payment", "delete_project"})

    def test_conversation_only(self) -> None:
        out = merge_blocking_categories(
            workspace_defaults=None,
            conversation_overrides=["publish"],
        )
        assert out == frozenset({"publish"})

    def test_union_preserves_workspace_floor(self) -> None:
        out = merge_blocking_categories(
            workspace_defaults=["payment"],
            conversation_overrides=["publish"],
        )
        assert out == frozenset({"payment", "publish"})

    def test_overlap_deduped(self) -> None:
        out = merge_blocking_categories(
            workspace_defaults=["payment", "publish"],
            conversation_overrides=["publish"],
        )
        assert out == frozenset({"payment", "publish"})

    def test_conversation_cannot_lower_workspace_floor(self) -> None:
        # Conversation override does not shrink the set — workspace
        # default remains in effect even if the conversation list omits it.
        out = merge_blocking_categories(
            workspace_defaults=["payment"],
            conversation_overrides=[],
        )
        assert "payment" in out
