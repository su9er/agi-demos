"""
Unit tests for HITL strategies.

Tests the HITL strategy classes in src/infrastructure/agent/hitl/hitl_strategies.py
"""

import pytest

from src.domain.model.agent.hitl_types import (
    HITLType,
    RiskLevel,
)
from src.infrastructure.agent.hitl.hitl_strategies import (
    ClarificationStrategy,
    DecisionStrategy,
    EnvVarStrategy,
    PermissionStrategy,
)


@pytest.mark.unit
class TestClarificationStrategy:
    """Test ClarificationStrategy."""

    def test_hitl_type(self):
        """Test strategy returns correct HITL type."""
        strategy = ClarificationStrategy()
        assert strategy.hitl_type == HITLType.CLARIFICATION

    def test_generate_request_id(self):
        """Test request ID generation has correct prefix."""
        strategy = ClarificationStrategy()
        request_id = strategy.generate_request_id()
        # The actual implementation uses "clar_" prefix
        assert request_id.startswith("clar_")
        assert len(request_id) > 5  # clar_ + uuid portion

    def test_create_request(self):
        """Test creating a clarification request."""
        strategy = ClarificationStrategy()
        request_data = {
            "question": "What approach should we use?",
            "clarification_type": "approach",
            "options": [
                {"id": "a", "label": "Approach A"},
                {"id": "b", "label": "Approach B"},
            ],
            "allow_custom": True,
        }

        request = strategy.create_request(
            conversation_id="conv-123",
            request_data=request_data,
            timeout_seconds=120,
        )

        assert request.hitl_type == HITLType.CLARIFICATION
        assert request.conversation_id == "conv-123"
        assert request.clarification_data is not None
        assert request.clarification_data.question == "What approach should we use?"
        assert len(request.clarification_data.options) == 2

    def test_create_request_with_string_options(self):
        """Test creating request with string options."""
        strategy = ClarificationStrategy()
        request_data = {
            "question": "Choose one",
            "clarification_type": "custom",
            "options": ["Option A", "Option B", "Option C"],
        }

        request = strategy.create_request(
            conversation_id="conv-123",
            request_data=request_data,
        )

        assert len(request.clarification_data.options) == 3
        assert request.clarification_data.options[0].label == "Option A"

    def test_extract_response_value_string(self):
        """Test extracting string response value."""
        strategy = ClarificationStrategy()
        response_data = {"answer": "option-a"}
        value = strategy.extract_response_value(response_data)
        assert value == "option-a"

    def test_extract_response_value_list(self):
        """Test extracting list response value."""
        strategy = ClarificationStrategy()
        response_data = {"answer": ["opt-1", "opt-2"]}
        value = strategy.extract_response_value(response_data)
        assert value == ["opt-1", "opt-2"]


@pytest.mark.unit
class TestDecisionStrategy:
    """Test DecisionStrategy."""

    def test_hitl_type(self):
        """Test strategy returns correct HITL type."""
        strategy = DecisionStrategy()
        assert strategy.hitl_type == HITLType.DECISION

    def test_generate_request_id(self):
        """Test request ID generation."""
        strategy = DecisionStrategy()
        request_id = strategy.generate_request_id()
        # The actual implementation uses "deci_" prefix
        assert request_id.startswith("deci_")

    def test_create_request(self):
        """Test creating a decision request."""
        strategy = DecisionStrategy()
        request_data = {
            "question": "Proceed with deployment?",
            "decision_type": "confirmation",
            "options": [
                {"id": "yes", "label": "Yes"},
                {"id": "no", "label": "No"},
            ],
            "default_option": "no",
        }

        request = strategy.create_request(
            conversation_id="conv-456",
            request_data=request_data,
        )

        assert request.hitl_type == HITLType.DECISION
        assert request.decision_data is not None
        assert request.decision_data.question == "Proceed with deployment?"
        assert request.decision_data.default_option == "no"

    def test_extract_response_value(self):
        """Test extracting decision response value."""
        strategy = DecisionStrategy()
        response_data = {"decision": "yes"}
        value = strategy.extract_response_value(response_data)
        assert value == "yes"


@pytest.mark.unit
class TestEnvVarStrategy:
    """Test EnvVarStrategy."""

    def test_hitl_type(self):
        """Test strategy returns correct HITL type."""
        strategy = EnvVarStrategy()
        assert strategy.hitl_type == HITLType.ENV_VAR

    def test_generate_request_id(self):
        """Test request ID generation."""
        strategy = EnvVarStrategy()
        request_id = strategy.generate_request_id()
        # The actual implementation uses "env_" prefix
        assert request_id.startswith("env_")

    def test_create_request(self):
        """Test creating an env var request."""
        strategy = EnvVarStrategy()
        request_data = {
            "tool_name": "github_search",
            "fields": [
                {
                    "name": "GITHUB_TOKEN",
                    "label": "GitHub Token",
                    "required": True,
                    "secret": True,
                    "input_type": "password",
                },
            ],
            "message": "GitHub requires authentication",
        }

        request = strategy.create_request(
            conversation_id="conv-789",
            request_data=request_data,
        )

        assert request.hitl_type == HITLType.ENV_VAR
        assert request.env_var_data is not None
        assert request.env_var_data.tool_name == "github_search"
        assert len(request.env_var_data.fields) == 1

    def test_extract_response_value(self):
        """Test extracting env var response values."""
        strategy = EnvVarStrategy()
        response_data = {
            "values": {"API_KEY": "secret123"},
            "save": True,
        }
        value = strategy.extract_response_value(response_data)
        assert value == {"API_KEY": "secret123"}

    def test_create_request_sanitizes_text_and_context(self):
        """Env-var requests should sanitize user-visible and contextual fields."""
        strategy = EnvVarStrategy()
        request = strategy.create_request(
            conversation_id="conv-env-sanitize",
            request_data={
                "tool_name": 'github<script>alert(1)</script>',
                "message": 'Need <b>token</b>',
                "context": {"note": '<img src=x onerror=alert(1)>', "count": 1},
                "fields": [
                    {
                        "name": 'API_<script>',
                        "label": '<b>API Key</b>',
                        "description": 'Paste <token>',
                        "placeholder": '<placeholder>',
                    }
                ],
            },
        )

        assert request.env_var_data is not None
        assert request.env_var_data.tool_name == "github&lt;script&gt;alert(1)&lt;/script&gt;"
        assert request.env_var_data.message == "Need &lt;b&gt;token&lt;/b&gt;"
        assert request.env_var_data.context["note"] == "&lt;img src=x onerror=alert(1)&gt;"
        assert request.env_var_data.fields[0].name == "API_&lt;script&gt;"
        assert request.env_var_data.fields[0].label == "&lt;b&gt;API Key&lt;/b&gt;"
        assert request.env_var_data.fields[0].description == "Paste &lt;token&gt;"
        assert request.env_var_data.fields[0].placeholder == "&lt;placeholder&gt;"


@pytest.mark.unit
class TestPermissionStrategy:
    """Test PermissionStrategy."""

    def test_hitl_type(self):
        """Test strategy returns correct HITL type."""
        strategy = PermissionStrategy()
        assert strategy.hitl_type == HITLType.PERMISSION

    def test_generate_request_id(self):
        """Test request ID generation."""
        strategy = PermissionStrategy()
        request_id = strategy.generate_request_id()
        # The actual implementation uses "perm_" prefix
        assert request_id.startswith("perm_")

    def test_create_request(self):
        """Test creating a permission request."""
        strategy = PermissionStrategy()
        request_data = {
            "tool_name": "terminal",
            "action": "execute_command",
            "risk_level": "high",
            "description": "Execute rm -rf",
        }

        request = strategy.create_request(
            conversation_id="conv-abc",
            request_data=request_data,
        )

        assert request.hitl_type == HITLType.PERMISSION
        assert request.permission_data is not None
        assert request.permission_data.tool_name == "terminal"
        assert request.permission_data.risk_level == RiskLevel.HIGH

    def test_extract_response_value_allow(self):
        """Test extracting permission allow response."""
        strategy = PermissionStrategy()
        response_data = {"action": "allow", "remember": False}
        value = strategy.extract_response_value(response_data)
        assert value is True

    def test_extract_response_value_deny(self):
        """Test extracting permission deny response."""
        strategy = PermissionStrategy()
        response_data = {"action": "deny", "remember": False}
        value = strategy.extract_response_value(response_data)
        assert value is False

    def test_extract_response_value_allow_always(self):
        """Test extracting permission allow_always response."""
        strategy = PermissionStrategy()
        response_data = {"action": "allow_always", "remember": True}
        value = strategy.extract_response_value(response_data)
        assert value is True

    def test_extract_response_value_conflicting_granted_flag_fails_closed(self):
        """Conflicting permission payloads must not resolve to allow."""
        strategy = PermissionStrategy()
        response_data = {"action": "deny", "granted": True}
        value = strategy.extract_response_value(response_data)
        assert value is False

    def test_create_request_sanitizes_text_and_context(self):
        """Permission requests should sanitize visible fields before persistence."""
        strategy = PermissionStrategy()
        request = strategy.create_request(
            conversation_id="conv-perm-sanitize",
            request_data={
                "tool_name": "terminal<script>",
                "action": "execute<script>",
                "risk_level": "medium",
                "description": "Run <b>command</b>",
                "details": {"cmd": "<rm -rf />"},
                "context": {"note": "<danger>"},
            },
        )

        assert request.permission_data is not None
        assert request.permission_data.tool_name == "terminal&lt;script&gt;"
        assert request.permission_data.action == "execute&lt;script&gt;"
        assert request.permission_data.description == "Run &lt;b&gt;command&lt;/b&gt;"
        assert request.permission_data.details["cmd"] == "&lt;rm -rf /&gt;"
        assert request.permission_data.context["note"] == "&lt;danger&gt;"
