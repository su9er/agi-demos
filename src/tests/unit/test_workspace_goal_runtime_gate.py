"""Unit tests for the Agent-First ``should_activate_workspace_authority`` gate.

Activation is driven solely by structural set-membership signals
(``has_workspace_binding``, ``has_open_root``). The user query is never
parsed — semantic classification lives in the sensing service and is
decided by an agent tool-call (see H2 of the Phase-5 Agent-First refactor).
"""

import pytest

from src.infrastructure.agent.workspace.workspace_goal_runtime import (
    should_activate_workspace_authority,
)


@pytest.mark.unit
class TestShouldActivateWorkspaceAuthority:
    def test_english_keywords_alone_do_not_activate(self) -> None:
        # Agent-First: keyword regex was removed. Without binding or
        # open-root, the activation gate stays off regardless of text.
        assert not should_activate_workspace_authority(
            "please execute the workspace goal",
        )

    def test_chinese_query_without_flags_does_not_activate(self) -> None:
        assert not should_activate_workspace_authority("帮我完成这个目标")

    def test_chinese_query_with_binding_activates(self) -> None:
        assert should_activate_workspace_authority(
            "帮我完成这个目标",
            has_workspace_binding=True,
        )

    def test_empty_query_with_open_root_activates(self) -> None:
        assert should_activate_workspace_authority("", has_open_root=True)

    def test_binding_short_circuits_regardless_of_query(self) -> None:
        assert should_activate_workspace_authority(
            "random chatter",
            has_workspace_binding=True,
        )

    def test_no_signals_returns_false(self) -> None:
        assert not should_activate_workspace_authority("just saying hi")

    def test_user_query_is_never_parsed(self) -> None:
        # Agent-First: prove the function is independent of text content.
        queries = [
            "please execute the workspace goal",
            "workspace autonomy decompose task now",
            "",
            "random chatter",
            "帮我完成这个目标",
        ]
        for q in queries:
            assert should_activate_workspace_authority(q) is False
            assert should_activate_workspace_authority(q, has_open_root=True) is True
