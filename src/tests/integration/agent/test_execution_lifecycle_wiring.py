"""Integration tests for execution.py lifecycle and background task wiring.

Verifies that _run_session_lifecycle correctly creates a
SessionLifecycleManager, calls run_lifecycle, commits the session,
and handles exceptions gracefully. Also verifies the module-level
_background_tasks set exists.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_lifecycle_result() -> MagicMock:
    """Create a mock LifecycleResult with expected attributes."""
    trim = MagicMock()
    trim.messages_before = 100
    trim.messages_after = 80

    archive = MagicMock()
    archive.archived_count = 5

    gc = MagicMock()
    gc.deleted_count = 3

    result = MagicMock()
    result.trim_results = [trim]
    result.archive_result = archive
    result.gc_result = gc
    return result


@pytest.mark.integration
class TestExecutionLifecycleWiring:
    """Tests for _run_session_lifecycle in execution.py."""

    async def test_run_session_lifecycle_calls_manager(self) -> None:
        """SessionLifecycleManager.run_lifecycle is called with project_id.

        Arrange: Patch async_session_factory, repos, and manager.
        Act: Call _run_session_lifecycle.
        Assert: run_lifecycle called with correct project_id.
        """
        # Arrange
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        lifecycle_result = _make_lifecycle_result()
        mock_manager_cls = MagicMock()
        mock_manager_instance = AsyncMock()
        mock_manager_instance.run_lifecycle = AsyncMock(return_value=lifecycle_result)
        mock_manager_cls.return_value = mock_manager_instance

        with (
            patch(
                "src.infrastructure.agent.actor.execution.async_session_factory",
                mock_factory,
            ),
            patch(
                "src.infrastructure.adapters.secondary.persistence"
                ".sql_conversation_repository.SqlConversationRepository",
                MagicMock(),
            ),
            patch(
                "src.infrastructure.adapters.secondary.persistence"
                ".sql_message_repository.SqlMessageRepository",
                MagicMock(),
            ),
            patch(
                "src.infrastructure.agent.session.lifecycle.SessionLifecycleManager",
                mock_manager_cls,
            ),
        ):
            from src.infrastructure.agent.actor.execution import (
                _run_session_lifecycle,
            )

            # Act
            await _run_session_lifecycle("proj-001")

        # Assert
        mock_manager_instance.run_lifecycle.assert_awaited_once_with("proj-001")

    async def test_run_session_lifecycle_commits_session(self) -> None:
        """DB session.commit() is called after successful lifecycle run.

        Arrange: Patch async_session_factory with mock session.
        Act: Call _run_session_lifecycle.
        Assert: session.commit() was awaited.
        """
        # Arrange
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        lifecycle_result = _make_lifecycle_result()
        mock_manager_cls = MagicMock()
        mock_manager_instance = AsyncMock()
        mock_manager_instance.run_lifecycle = AsyncMock(return_value=lifecycle_result)
        mock_manager_cls.return_value = mock_manager_instance

        with (
            patch(
                "src.infrastructure.agent.actor.execution.async_session_factory",
                mock_factory,
            ),
            patch(
                "src.infrastructure.adapters.secondary.persistence"
                ".sql_conversation_repository.SqlConversationRepository",
                MagicMock(),
            ),
            patch(
                "src.infrastructure.adapters.secondary.persistence"
                ".sql_message_repository.SqlMessageRepository",
                MagicMock(),
            ),
            patch(
                "src.infrastructure.agent.session.lifecycle.SessionLifecycleManager",
                mock_manager_cls,
            ),
        ):
            from src.infrastructure.agent.actor.execution import (
                _run_session_lifecycle,
            )

            # Act
            await _run_session_lifecycle("proj-002")

        # Assert
        mock_session.commit.assert_awaited_once()

    async def test_run_session_lifecycle_handles_exception(self) -> None:
        """Exception inside lifecycle is caught; no unhandled propagation.

        Arrange: Mock manager.run_lifecycle to raise.
        Act: Call _run_session_lifecycle.
        Assert: No exception propagates.
        """
        # Arrange
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        mock_manager_cls = MagicMock()
        mock_manager_instance = AsyncMock()
        mock_manager_instance.run_lifecycle = AsyncMock(
            side_effect=RuntimeError("db connection lost")
        )
        mock_manager_cls.return_value = mock_manager_instance

        with (
            patch(
                "src.infrastructure.agent.actor.execution.async_session_factory",
                mock_factory,
            ),
            patch(
                "src.infrastructure.adapters.secondary.persistence"
                ".sql_conversation_repository.SqlConversationRepository",
                MagicMock(),
            ),
            patch(
                "src.infrastructure.adapters.secondary.persistence"
                ".sql_message_repository.SqlMessageRepository",
                MagicMock(),
            ),
            patch(
                "src.infrastructure.agent.session.lifecycle.SessionLifecycleManager",
                mock_manager_cls,
            ),
        ):
            from src.infrastructure.agent.actor.execution import (
                _run_session_lifecycle,
            )

            # Act -- should NOT raise
            await _run_session_lifecycle("proj-003")

        # Assert -- if we got here, exception was caught
        mock_session.commit.assert_not_awaited()

    async def test_background_tasks_set_exists(self) -> None:
        """Module-level _background_tasks is a set[asyncio.Task].

        Arrange: Import execution module.
        Act: Access _background_tasks.
        Assert: It is a set instance.
        """
        # Arrange & Act
        from src.infrastructure.agent.actor.execution import (
            _background_tasks,
        )

        # Assert
        assert isinstance(_background_tasks, set)
