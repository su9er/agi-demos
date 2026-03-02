"""Integration tests for SkillMCPManager wiring and interface contract."""

from __future__ import annotations

import pytest

from src.infrastructure.agent.mcp.skill_mcp_manager import (
    SkillMCPConfig,
    SkillMCPManager,
)


@pytest.mark.integration
class TestSkillMCPManagerWiring:
    """Verify SkillMCPManager instantiation and public interface."""

    def test_skill_mcp_manager_importable(self) -> None:
        """SkillMCPManager can be imported and instantiated."""
        # Arrange / Act
        manager = SkillMCPManager()

        # Assert
        assert manager is not None
        assert manager.active_skills == frozenset()
        assert manager.active_servers == frozenset()

    def test_skill_mcp_manager_has_required_interface(self) -> None:
        """SkillMCPManager exposes all expected public methods."""
        # Arrange
        manager = SkillMCPManager()
        expected_methods = [
            "register_skill_mcps",
            "activate_skill",
            "deactivate_skill",
            "shutdown",
            "get_skill_tools",
            "health_check",
        ]

        # Act / Assert
        for method_name in expected_methods:
            attr = getattr(manager, method_name, None)
            assert attr is not None, f"Missing method: {method_name}"
            assert callable(attr), f"{method_name} is not callable"

    def test_register_and_get_tools_returns_empty_for_skill(
        self,
    ) -> None:
        """After registering configs, get_skill_tools returns empty list
        when no servers have been activated."""
        # Arrange
        manager = SkillMCPManager()
        config = SkillMCPConfig(
            server_name="test-server",
            command="echo",
            args=["hello"],
        )

        # Act
        manager.register_skill_mcps("my-skill", [config])
        tools = manager.get_skill_tools("my-skill")

        # Assert
        assert tools == []
        assert "my-skill" not in manager.active_skills

    def test_skill_mcp_config_creation(self) -> None:
        """SkillMCPConfig can be created with expected fields."""
        # Arrange / Act
        config = SkillMCPConfig(
            server_name="fetch-server",
            command="npx",
            args=["-y", "@anthropic/mcp-server-fetch"],
            env={"NODE_ENV": "test"},
            auto_start=False,
        )

        # Assert
        assert config.server_name == "fetch-server"
        assert config.command == "npx"
        assert config.args == ["-y", "@anthropic/mcp-server-fetch"]
        assert config.env == {"NODE_ENV": "test"}
        assert config.auto_start is False

    def test_register_raises_on_empty_skill_id(self) -> None:
        """register_skill_mcps raises ValueError for empty skill_id."""
        # Arrange
        manager = SkillMCPManager()
        config = SkillMCPConfig(server_name="s1", command="echo")

        # Act / Assert
        with pytest.raises(ValueError, match="skill_id"):
            manager.register_skill_mcps("", [config])

    def test_register_raises_on_empty_configs(self) -> None:
        """register_skill_mcps raises ValueError for empty configs."""
        # Arrange
        manager = SkillMCPManager()

        # Act / Assert
        with pytest.raises(ValueError, match="configs"):
            manager.register_skill_mcps("skill-1", [])
