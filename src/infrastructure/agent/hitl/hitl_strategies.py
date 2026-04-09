"""HITL Type Strategies for Human-in-the-Loop operations.

Strategy pattern implementations for handling different HITL request types
(clarification, decision, env_var, permission).
"""

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any

from src.domain.model.agent.hitl_types import (
    A2UIActionRequestData,
    ClarificationOption,
    ClarificationType,
    DecisionOption,
    DecisionType,
    EnvVarField,
    HITLRequest,
    HITLType,
    PermissionAction,
    RiskLevel,
    create_clarification_request,
    create_decision_request,
    create_env_var_request,
    create_permission_request,
)
from src.infrastructure.agent.hitl.utils import sanitize_hitl_context, sanitize_hitl_text

logger = logging.getLogger(__name__)


class HITLTypeStrategy(ABC):
    """Base strategy for handling a specific HITL type."""

    @property
    @abstractmethod
    def hitl_type(self) -> HITLType:
        """Get the HITL type this strategy handles."""

    @abstractmethod
    def generate_request_id(self) -> str:
        """Generate a unique request ID."""

    @abstractmethod
    def create_request(
        self,
        conversation_id: str,
        request_data: dict[str, Any],
        **kwargs: Any,
    ) -> HITLRequest:
        """Create an HITL request from raw data."""

    @abstractmethod
    def extract_response_value(
        self,
        response_data: dict[str, Any],
    ) -> Any:
        """Extract the usable response value from response data."""

    @abstractmethod
    def get_default_response(
        self,
        request: HITLRequest,
    ) -> Any:
        """Get a default response for timeout scenarios."""


class ClarificationStrategy(HITLTypeStrategy):
    """Strategy for clarification requests."""

    @property
    def hitl_type(self) -> HITLType:
        return HITLType.CLARIFICATION

    def generate_request_id(self) -> str:
        return f"clar_{uuid.uuid4().hex[:8]}"

    def create_request(
        self,
        conversation_id: str,
        request_data: dict[str, Any],
        **kwargs: Any,
    ) -> HITLRequest:
        question = sanitize_hitl_text(request_data.get("question", "")) or ""
        options_data = request_data.get("options", []) or []
        clarification_type = ClarificationType(request_data.get("clarification_type", "custom"))

        options: list[ClarificationOption] = []
        for opt in options_data:
            if isinstance(opt, dict):
                label = sanitize_hitl_text(opt.get("label", ""))
                if label is None:
                    continue
                options.append(
                    ClarificationOption(
                        id=str(opt.get("id", str(len(options)))).strip() or str(len(options)),
                        label=label,
                        description=sanitize_hitl_text(opt.get("description")),
                        recommended=opt.get("recommended", False),
                    )
                )
            elif isinstance(opt, str):
                label = sanitize_hitl_text(opt)
                if label is None:
                    continue
                options.append(
                    ClarificationOption(
                        id=str(len(options)),
                        label=label,
                    )
                )

        # Auto-enable allow_custom when options are empty
        allow_custom = request_data.get("allow_custom", True)
        if not options:
            allow_custom = True
        request_id = request_data.get("_request_id") or self.generate_request_id()

        return create_clarification_request(
            request_id=request_id,
            conversation_id=conversation_id,
            question=question,
            options=options,
            clarification_type=clarification_type,
            allow_custom=allow_custom,
            timeout_seconds=kwargs.get("timeout_seconds", 300.0),
            tenant_id=kwargs.get("tenant_id"),
            project_id=kwargs.get("project_id"),
            message_id=kwargs.get("message_id"),
            context=sanitize_hitl_context(request_data.get("context", {})),
        )

    def extract_response_value(self, response_data: dict[str, Any]) -> Any:
        if isinstance(response_data, str):
            return sanitize_hitl_text(response_data) or ""
        if not isinstance(response_data, dict):
            return ""
        answer = response_data.get("answer", "")
        if isinstance(answer, list):
            sanitized_answers: list[str] = []
            for item in answer:
                sanitized_item = sanitize_hitl_text(item)
                if sanitized_item is not None:
                    sanitized_answers.append(sanitized_item)
            return sanitized_answers
        return sanitize_hitl_text(answer) or ""

    def get_default_response(self, request: HITLRequest) -> Any:
        if request.clarification_data and request.clarification_data.default_value:
            return request.clarification_data.default_value
        if request.clarification_data and request.clarification_data.options:
            for opt in request.clarification_data.options:
                if opt.recommended:
                    return opt.id
            return request.clarification_data.options[0].id
        return ""


class DecisionStrategy(HITLTypeStrategy):
    """Strategy for decision requests."""

    @property
    def hitl_type(self) -> HITLType:
        return HITLType.DECISION

    def generate_request_id(self) -> str:
        return f"deci_{uuid.uuid4().hex[:8]}"

    def create_request(
        self,
        conversation_id: str,
        request_data: dict[str, Any],
        **kwargs: Any,
    ) -> HITLRequest:
        question = sanitize_hitl_text(request_data.get("question", "")) or ""
        options_data = request_data.get("options", []) or []
        decision_type_str = request_data.get("decision_type", "single_choice")
        selection_mode = request_data.get("selection_mode", "single")
        if selection_mode == "multiple":
            decision_type = DecisionType("multi_choice")
        else:
            decision_type = DecisionType(decision_type_str)

        options: list[DecisionOption] = []
        for opt in options_data:
            if isinstance(opt, dict):
                risk_level = None
                if opt.get("risk_level"):
                    risk_level = RiskLevel(opt["risk_level"])
                label = sanitize_hitl_text(opt.get("label", ""))
                if label is None:
                    continue
                sanitized_risks: list[str] = []
                raw_risks = opt.get("risks", [])
                if isinstance(raw_risks, list):
                    for raw_risk in raw_risks:
                        sanitized_risk = sanitize_hitl_text(raw_risk)
                        if sanitized_risk is not None:
                            sanitized_risks.append(sanitized_risk)

                options.append(
                    DecisionOption(
                        id=str(opt.get("id", str(len(options)))).strip() or str(len(options)),
                        label=label,
                        description=sanitize_hitl_text(opt.get("description")),
                        recommended=opt.get("recommended", False),
                        risk_level=risk_level,
                        estimated_time=sanitize_hitl_text(opt.get("estimated_time")),
                        estimated_cost=sanitize_hitl_text(opt.get("estimated_cost")),
                        risks=sanitized_risks,
                    )
                )
            elif isinstance(opt, str):
                label = sanitize_hitl_text(opt)
                if label is None:
                    continue
                options.append(
                    DecisionOption(
                        id=str(len(options)),
                        label=label,
                    )
                )

        # Auto-enable allow_custom when options are empty
        allow_custom = request_data.get("allow_custom", False)
        if not options:
            allow_custom = True
        request_id = request_data.get("_request_id") or self.generate_request_id()

        return create_decision_request(
            request_id=request_id,
            conversation_id=conversation_id,
            question=question,
            options=options,
            decision_type=decision_type,
            allow_custom=allow_custom,
            timeout_seconds=kwargs.get("timeout_seconds", 300.0),
            tenant_id=kwargs.get("tenant_id"),
            project_id=kwargs.get("project_id"),
            message_id=kwargs.get("message_id"),
            context=sanitize_hitl_context(request_data.get("context", {})),
            default_option=request_data.get("default_option"),
            max_selections=request_data.get("max_selections"),
        )

    def extract_response_value(self, response_data: dict[str, Any]) -> Any:
        if isinstance(response_data, str):
            return sanitize_hitl_text(response_data) or ""
        if not isinstance(response_data, dict):
            return ""
        decision = response_data.get("decision", "")
        if isinstance(decision, list):
            sanitized_decisions: list[str] = []
            for item in decision:
                sanitized_item = sanitize_hitl_text(item)
                if sanitized_item is not None:
                    sanitized_decisions.append(sanitized_item)
            return sanitized_decisions
        return sanitize_hitl_text(decision) or ""

    def get_default_response(self, request: HITLRequest) -> Any:
        if request.decision_data and request.decision_data.default_option:
            return request.decision_data.default_option
        if request.decision_data and request.decision_data.options:
            for opt in request.decision_data.options:
                if opt.recommended:
                    return opt.id
            return request.decision_data.options[0].id
        return ""


class EnvVarStrategy(HITLTypeStrategy):
    """Strategy for environment variable requests."""

    @property
    def hitl_type(self) -> HITLType:
        return HITLType.ENV_VAR

    def generate_request_id(self) -> str:
        return f"env_{uuid.uuid4().hex[:8]}"

    def create_request(
        self,
        conversation_id: str,
        request_data: dict[str, Any],
        **kwargs: Any,
    ) -> HITLRequest:
        from src.domain.model.agent.hitl_types import EnvVarInputType

        tool_name = sanitize_hitl_text(request_data.get("tool_name", "unknown")) or "unknown"
        fields_data = request_data.get("fields", [])
        message = sanitize_hitl_text(request_data.get("message"))

        fields = []
        for f in fields_data:
            if isinstance(f, dict):
                input_type = EnvVarInputType.TEXT
                if f.get("input_type"):
                    try:
                        input_type = EnvVarInputType(f["input_type"])
                    except ValueError:
                        input_type = EnvVarInputType.TEXT
                elif f.get("secret"):
                    input_type = EnvVarInputType.PASSWORD

                name = sanitize_hitl_text(f.get("name", "")) or ""
                label = sanitize_hitl_text(f.get("label", f.get("name", ""))) or name

                fields.append(
                    EnvVarField(
                        name=name,
                        label=label,
                        description=sanitize_hitl_text(f.get("description")),
                        required=bool(f.get("required", True)),
                        secret=bool(f.get("secret", False)),
                        input_type=input_type,
                        default_value=sanitize_hitl_text(f.get("default_value")),
                        placeholder=sanitize_hitl_text(f.get("placeholder")),
                        pattern=sanitize_hitl_text(f.get("pattern")),
                    )
                )

        request_id = request_data.get("_request_id") or self.generate_request_id()
        return create_env_var_request(
            request_id=request_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            fields=fields,
            message=message,
            timeout_seconds=kwargs.get("timeout_seconds", 300.0),
            tenant_id=kwargs.get("tenant_id"),
            project_id=kwargs.get("project_id"),
            message_id=kwargs.get("message_id"),
            context=sanitize_hitl_context(request_data.get("context", {})),
            allow_save=request_data.get("allow_save", True),
        )

    def extract_response_value(self, response_data: dict[str, Any]) -> Any:
        if isinstance(response_data, str):
            return response_data
        return response_data.get("values", {})

    def get_default_response(self, request: HITLRequest) -> Any:
        return {}


class PermissionStrategy(HITLTypeStrategy):
    """Strategy for permission requests."""

    @property
    def hitl_type(self) -> HITLType:
        return HITLType.PERMISSION

    def generate_request_id(self) -> str:
        return f"perm_{uuid.uuid4().hex[:8]}"

    def create_request(
        self,
        conversation_id: str,
        request_data: dict[str, Any],
        **kwargs: Any,
    ) -> HITLRequest:
        tool_name = sanitize_hitl_text(request_data.get("tool_name", "unknown")) or "unknown"
        action = sanitize_hitl_text(request_data.get("action", "execute")) or "execute"
        risk_level = RiskLevel(request_data.get("risk_level", "medium"))

        default_action = None
        if request_data.get("default_action"):
            default_action = PermissionAction(request_data["default_action"])

        request_id = request_data.get("_request_id") or self.generate_request_id()
        return create_permission_request(
            request_id=request_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            action=action,
            risk_level=risk_level,
            timeout_seconds=kwargs.get("timeout_seconds", 60.0),
            tenant_id=kwargs.get("tenant_id"),
            project_id=kwargs.get("project_id"),
            message_id=kwargs.get("message_id"),
            details=sanitize_hitl_context(request_data.get("details", {})),
            description=sanitize_hitl_text(request_data.get("description")),
            allow_remember=request_data.get("allow_remember", True),
            default_action=default_action,
            context=sanitize_hitl_context(request_data.get("context", {})),
        )

    def extract_response_value(self, response_data: dict[str, Any]) -> Any:
        if isinstance(response_data, str):
            return response_data in ("allow", "allow_always")
        action = response_data.get("action", "deny")
        if isinstance(action, str) and action in {permission.value for permission in PermissionAction}:
            granted = response_data.get("granted")
            if isinstance(granted, bool) and granted is not (
                action in ("allow", "allow_always")
            ):
                return False
            return action in ("allow", "allow_always")
        granted = response_data.get("granted")
        if isinstance(granted, bool):
            return granted
        return False

    def get_default_response(self, request: HITLRequest) -> Any:
        if request.permission_data and request.permission_data.default_action:
            return request.permission_data.default_action.value in (
                "allow",
                "allow_always",
            )
        return False


class A2UIActionStrategy(HITLTypeStrategy):
    """Strategy for A2UI interactive surface action requests.

    When the agent renders an interactive A2UI surface and needs to wait
    for the user to interact (click a button, submit a form, etc.).
    """

    @property
    def hitl_type(self) -> HITLType:
        return HITLType.A2UI_ACTION

    def generate_request_id(self) -> str:
        return f"a2ui_{uuid.uuid4().hex[:8]}"

    def create_request(
        self,
        conversation_id: str,
        request_data: dict[str, Any],
        **kwargs: Any,
    ) -> HITLRequest:
        """Create an HITL request for an A2UI interactive surface.

        request_data should contain:
          - block_id: Canvas block ID housing the A2UI surface
          - title: Human-readable surface title
          - components: JSONL component definitions (for persistence/debug)
          - context: Arbitrary metadata
        """
        return HITLRequest(
            request_id=self.generate_request_id(),
            hitl_type=HITLType.A2UI_ACTION,
            conversation_id=conversation_id,
            timeout_seconds=kwargs.get("timeout_seconds", 300.0),
            tenant_id=kwargs.get("tenant_id"),
            project_id=kwargs.get("project_id"),
            message_id=kwargs.get("message_id"),
            a2ui_data=A2UIActionRequestData(
                title=request_data.get("title", "A2UI interaction required"),
                block_id=request_data.get("block_id", ""),
                context=request_data.get("context", {}),
            ),
        )

    def extract_response_value(self, response_data: dict[str, Any]) -> Any:
        """Extract the action details from the frontend response.

        Expected shape from A2UISurfaceRenderer:
          {"action_name": str, "source_component_id": str, "context": dict}
        """
        if isinstance(response_data, dict):
            return {
                "action_name": response_data.get("action_name", ""),
                "source_component_id": response_data.get("source_component_id", ""),
                "context": response_data.get("context", {}),
            }
        return {"action_name": "", "source_component_id": "", "context": {}}

    def get_default_response(self, request: HITLRequest) -> Any:
        """Default response when the A2UI surface times out or is cancelled."""
        return {"action_name": "", "cancelled": True}
