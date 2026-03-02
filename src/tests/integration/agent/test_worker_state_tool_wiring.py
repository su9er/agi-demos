"""Integration tests for _add_session_comm_tools and _add_canvas_tools wiring.

Verifies that agent_worker_state helper functions correctly register
session comm and canvas tools into the tool dictionary, and degrade
gracefully on import/setup failures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.integration
class TestSessionCommToolsWiring:
    """Tests for _add_session_comm_tools adding tools to the dict."""

    async def test_session_comm_tools_added(self) -> None:
        """Tools are added to the dict after configure_session_comm.

        Arrange: Patch imports to provide mock objects.
        Act: Call _add_session_comm_tools.
        Assert: Three tool keys present in tools dict.
        """
        # Arrange
        mock_session = MagicMock()
        mock_session_factory = MagicMock(return_value=mock_session)

        mock_list_tool = MagicMock()
        mock_list_tool.name = "sessions_list"
        mock_history_tool = MagicMock()
        mock_history_tool.name = "sessions_history"
        mock_send_tool = MagicMock()
        mock_send_tool.name = "sessions_send"
        mock_configure = MagicMock()

        tools: dict[str, Any] = {}

        with (
            patch(
                "src.infrastructure.agent.state.agent_worker_state.SessionCommService",
                create=True,
            ),
            patch(
                "src.infrastructure.agent.state.agent_worker_state.async_session_factory",
                mock_session_factory,
                create=True,
            ),
            patch(
                "src.infrastructure.agent.state.agent_worker_state.SqlConversationRepository",
                create=True,
            ),
            patch(
                "src.infrastructure.agent.state.agent_worker_state.SqlMessageRepository",
                create=True,
            ),
            patch(
                "src.infrastructure.agent.state.agent_worker_state.configure_session_comm",
                mock_configure,
                create=True,
            ),
            patch(
                "src.infrastructure.agent.state.agent_worker_state.sessions_list_tool",
                mock_list_tool,
                create=True,
            ),
            patch(
                "src.infrastructure.agent.state.agent_worker_state.sessions_history_tool",
                mock_history_tool,
                create=True,
            ),
            patch(
                "src.infrastructure.agent.state.agent_worker_state.sessions_send_tool",
                mock_send_tool,
                create=True,
            ),
        ):
            # The function uses lazy imports, so we import here
            from src.infrastructure.agent.state.agent_worker_state import (
                _add_session_comm_tools,
            )

            # Act
            _add_session_comm_tools(tools, project_id="proj-001", redis_client=MagicMock())

        # Assert
        assert "sessions_list" in tools
        assert "sessions_history" in tools
        assert "sessions_send" in tools
        assert len(tools) == 3

    async def test_session_comm_tools_graceful_failure(self) -> None:
        """Import failure is caught silently; tools dict unchanged.

        Arrange: Patch lazy import to raise ImportError.
        Act: Call _add_session_comm_tools.
        Assert: tools dict is empty, no exception raised.
        """
        # Arrange
        tools: dict[str, Any] = {}

        # Patch sys.modules so the lazy import inside
        # _add_session_comm_tools raises ImportError.
        with patch.dict(
            "sys.modules",
            {
                "src.application.services.session_comm_service": None,
            },
        ):
            import src.infrastructure.agent.state.agent_worker_state as mod

            mod._add_session_comm_tools(tools, project_id="proj-001", redis_client=MagicMock())

        # Assert -- no error raised, tools still empty
        assert len(tools) == 0


@pytest.mark.integration
class TestCanvasToolsWiring:
    """Tests for _add_canvas_tools adding tools to the dict."""

    async def test_canvas_tools_added(self) -> None:
        """Canvas tools are added to the dict after configure_canvas.

        Arrange: Patch canvas imports to provide mock objects.
        Act: Call _add_canvas_tools.
        Assert: Three canvas tool keys present in tools dict.
        """
        # Arrange
        mock_manager_cls = MagicMock()
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager

        mock_create = MagicMock()
        mock_create.name = "canvas_create"
        mock_update = MagicMock()
        mock_update.name = "canvas_update"
        mock_delete = MagicMock()
        mock_delete.name = "canvas_delete"
        mock_configure = MagicMock()

        tools: dict[str, Any] = {}

        with (
            patch(
                "src.infrastructure.agent.canvas.manager.CanvasManager",
                mock_manager_cls,
            ),
            patch(
                "src.infrastructure.agent.canvas.tools.canvas_create",
                mock_create,
            ),
            patch(
                "src.infrastructure.agent.canvas.tools.canvas_update",
                mock_update,
            ),
            patch(
                "src.infrastructure.agent.canvas.tools.canvas_delete",
                mock_delete,
            ),
            patch(
                "src.infrastructure.agent.canvas.tools.configure_canvas",
                mock_configure,
            ),
        ):
            from src.infrastructure.agent.state.agent_worker_state import (
                _add_canvas_tools,
            )

            # Act
            _add_canvas_tools(tools)

        # Assert
        assert "canvas_create" in tools
        assert "canvas_update" in tools
        assert "canvas_delete" in tools
        assert len(tools) == 3
        mock_configure.assert_called_once_with(mock_manager)

    async def test_canvas_tools_graceful_failure(self) -> None:
        """Import failure is caught silently; tools dict unchanged.

        Arrange: Patch sys.modules to make canvas import fail.
        Act: Call _add_canvas_tools.
        Assert: tools dict is empty, no exception raised.
        """
        # Arrange
        tools: dict[str, Any] = {}

        with patch.dict(
            "sys.modules",
            {
                "src.infrastructure.agent.canvas.manager": None,
            },
        ):
            import src.infrastructure.agent.state.agent_worker_state as mod

            # Act
            mod._add_canvas_tools(tools)

        # Assert -- no error raised, tools still empty
        assert len(tools) == 0
