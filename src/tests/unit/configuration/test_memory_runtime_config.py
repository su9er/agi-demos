from __future__ import annotations

import pytest

from src.configuration.config import Settings


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["plugin", "disabled", "legacy", "dual"])
def test_settings_accept_agent_memory_runtime_mode_values(mode: str) -> None:
    settings = Settings(AGENT_MEMORY_RUNTIME_MODE=mode)
    assert settings.agent_memory_runtime_mode == mode


@pytest.mark.unit
def test_settings_reject_invalid_agent_memory_runtime_mode() -> None:
    with pytest.raises(ValueError, match="AGENT_MEMORY_RUNTIME_MODE"):
        Settings(AGENT_MEMORY_RUNTIME_MODE="unknown")


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["plugin", "disabled"])
def test_settings_accept_agent_memory_tool_provider_mode_values(mode: str) -> None:
    settings = Settings(AGENT_MEMORY_TOOL_PROVIDER_MODE=mode)
    assert settings.agent_memory_tool_provider_mode == mode


@pytest.mark.unit
def test_settings_normalize_legacy_agent_memory_tool_provider_mode_to_plugin() -> None:
    settings = Settings(AGENT_MEMORY_TOOL_PROVIDER_MODE="legacy")
    assert settings.agent_memory_tool_provider_mode == "plugin"


@pytest.mark.unit
def test_settings_reject_invalid_agent_memory_tool_provider_mode() -> None:
    with pytest.raises(ValueError, match="AGENT_MEMORY_TOOL_PROVIDER_MODE"):
        Settings(AGENT_MEMORY_TOOL_PROVIDER_MODE="unknown")
