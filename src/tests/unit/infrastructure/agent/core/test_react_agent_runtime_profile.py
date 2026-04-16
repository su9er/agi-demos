"""Tests for ReActAgent runtime profile max-step resolution."""

import pytest

from src.domain.model.agent.agent_definition import Agent
from src.domain.model.agent.tenant_agent_config import TenantAgentConfig
from src.infrastructure.agent.core.react_agent import ReActAgent


def _make_agent(**overrides) -> Agent:
    return Agent.create(
        tenant_id="tenant-1",
        project_id="project-1",
        name="test-agent",
        display_name="Test Agent",
        system_prompt="You are a test agent.",
        **overrides,
    )


@pytest.mark.unit
class TestReActAgentRuntimeProfile:
    def test_uses_tenant_max_steps_for_legacy_default_agent_iterations(self) -> None:
        agent = ReActAgent(model="test-model", tools={})
        tenant_config = TenantAgentConfig.create_default("tenant-1")
        tenant_config_data = tenant_config.to_dict() | {"max_work_plan_steps": 4999}
        selected_agent = _make_agent(max_iterations=10)

        profile = agent._build_runtime_profile(
            tenant_id="tenant-1",
            tenant_agent_config_data=tenant_config_data,
            selected_agent=selected_agent,
        )

        assert profile.effective_max_steps == 4999

    def test_uses_agent_max_steps_when_explicitly_marked(self) -> None:
        agent = ReActAgent(model="test-model", tools={})
        tenant_config = TenantAgentConfig.create_default("tenant-1")
        tenant_config_data = tenant_config.to_dict() | {"max_work_plan_steps": 4999}
        selected_agent = _make_agent(
            max_iterations=10,
            metadata={"max_iterations_explicit": True},
        )

        profile = agent._build_runtime_profile(
            tenant_id="tenant-1",
            tenant_agent_config_data=tenant_config_data,
            selected_agent=selected_agent,
        )

        assert profile.effective_max_steps == 10
