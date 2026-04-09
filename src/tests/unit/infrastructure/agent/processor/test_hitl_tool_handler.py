"""Unit tests for HITL tool handler answered events."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.events.agent_events import (
    AgentA2UIActionAskedEvent,
    AgentCanvasUpdatedEvent,
    AgentClarificationAnsweredEvent,
    AgentDecisionAnsweredEvent,
    AgentEnvVarProvidedEvent,
    AgentObserveEvent,
)
from src.infrastructure.agent.canvas.manager import CanvasManager
from src.infrastructure.agent.canvas.tools import configure_canvas
from src.infrastructure.agent.core.message import ToolPart, ToolState
from src.infrastructure.agent.processor.hitl_tool_handler import (
    handle_a2ui_action_tool,
    handle_clarification_tool,
    handle_decision_tool,
    handle_env_var_tool,
)


def _make_tool_part(call_id: str, tool_name: str) -> ToolPart:
    return ToolPart(
        call_id=call_id,
        tool=tool_name,
        status=ToolState.RUNNING,
        input={},
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_clarification_answered_event_uses_original_request_id() -> None:
    coordinator = MagicMock()
    coordinator.prepare_request = AsyncMock(return_value="clar-req-1")
    coordinator.wait_for_response = AsyncMock(return_value="PostgreSQL")
    tool_part = _make_tool_part("call-clar", "ask_clarification")

    events = [
        event
        async for event in handle_clarification_tool(
            coordinator=coordinator,
            call_id="call-clar",
            tool_name="ask_clarification",
            arguments={
                "question": "Which DB?",
                "clarification_type": "approach",
                "options": [{"id": "pg", "label": "PostgreSQL"}],
            },
            tool_part=tool_part,
        )
    ]

    answered_event = next(e for e in events if isinstance(e, AgentClarificationAnsweredEvent))
    assert answered_event.request_id == "clar-req-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decision_answered_event_uses_original_request_id() -> None:
    coordinator = MagicMock()
    coordinator.prepare_request = AsyncMock(return_value="dec-req-1")
    coordinator.wait_for_response = AsyncMock(return_value="option_a")
    tool_part = _make_tool_part("call-dec", "request_decision")

    events = [
        event
        async for event in handle_decision_tool(
            coordinator=coordinator,
            call_id="call-dec",
            tool_name="request_decision",
            arguments={
                "question": "Choose option",
                "decision_type": "method",
                "options": [{"id": "a", "label": "Option A"}],
            },
            tool_part=tool_part,
        )
    ]

    answered_event = next(e for e in events if isinstance(e, AgentDecisionAnsweredEvent))
    assert answered_event.request_id == "dec-req-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_env_var_provided_event_uses_original_request_id() -> None:
    coordinator = MagicMock()
    coordinator.prepare_request = AsyncMock(return_value="env-req-1")
    coordinator.wait_for_response = AsyncMock(return_value={"API_KEY": "secret"})
    tool_part = _make_tool_part("call-env", "request_env_var")

    events = [
        event
        async for event in handle_env_var_tool(
            coordinator=coordinator,
            call_id="call-env",
            tool_name="request_env_var",
            arguments={
                "tool_name": "web_search",
                "fields": [{"name": "API_KEY", "description": "Key"}],
            },
            tool_part=tool_part,
        )
    ]

    provided_event = next(e for e in events if isinstance(e, AgentEnvVarProvidedEvent))
    assert provided_event.request_id == "env-req-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a2ui_tool_infers_surface_id_for_canvas_metadata() -> None:
    coordinator = MagicMock()
    coordinator.conversation_id = "conv-a2ui"
    coordinator.prepare_request = AsyncMock(return_value="a2ui-req-1")
    coordinator.wait_for_response = AsyncMock(
        return_value={
            "action_name": "submit",
            "source_component_id": "button-1",
            "context": {"approved": True},
        }
    )
    tool_part = _make_tool_part("call-a2ui", "canvas_create_interactive")
    configure_canvas(CanvasManager())

    components = "\n".join(
        [
            '{"beginRendering":{"surfaceId":"surface-99","root":"root-1"}}',
            '{"surfaceUpdate":{"surfaceId":"surface-99","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}',
        ]
    )

    events = [
        event
        async for event in handle_a2ui_action_tool(
            coordinator=coordinator,
            call_id="call-a2ui",
            tool_name="canvas_create_interactive",
            arguments={"title": "Review", "components": components},
            tool_part=tool_part,
        )
    ]

    canvas_event = next(e for e in events if isinstance(e, AgentCanvasUpdatedEvent))
    asked_event = next(e for e in events if isinstance(e, AgentA2UIActionAskedEvent))

    assert canvas_event.block is not None
    assert canvas_event.block["metadata"]["surface_id"] == "surface-99"
    assert canvas_event.block["metadata"]["hitl_request_id"] == "a2ui-req-1"
    assert asked_event.block_id == canvas_event.block_id

    configure_canvas(None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a2ui_tool_reuses_existing_canvas_block() -> None:
    coordinator = MagicMock()
    coordinator.conversation_id = "conv-a2ui"
    coordinator.prepare_request = AsyncMock(return_value="a2ui-req-2")
    coordinator.wait_for_response = AsyncMock(
        return_value={
            "action_name": "submit",
            "source_component_id": "button-1",
            "context": {"approved": True},
        }
    )
    manager = CanvasManager()
    existing = manager.create_block(
        conversation_id="conv-a2ui",
        block_type="a2ui_surface",
        title="Existing",
        content='{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
        metadata={"surface_id": "surface-1"},
    )
    configure_canvas(manager)
    tool_part = _make_tool_part("call-a2ui", "canvas_create_interactive")

    components = "\n".join(
        [
            '{"beginRendering":{"surfaceId":"surface-1","root":"root-2"}}',
            '{"surfaceUpdate":{"surfaceId":"surface-1","components":[{"id":"root-2","component":{"Text":{"text":{"literal":"updated"}}}}]}}',
        ]
    )

    events = [
        event
        async for event in handle_a2ui_action_tool(
            coordinator=coordinator,
            call_id="call-a2ui",
            tool_name="canvas_create_interactive",
            arguments={"title": "Review", "components": components, "block_id": existing.id},
            tool_part=tool_part,
        )
    ]

    canvas_events = [e for e in events if isinstance(e, AgentCanvasUpdatedEvent)]
    assert canvas_events[0].action == "updated"
    assert canvas_events[0].block_id == existing.id
    assert canvas_events[0].block is not None
    assert canvas_events[0].block["metadata"]["hitl_request_id"] == "a2ui-req-2"
    assert canvas_events[-1].block is not None
    assert canvas_events[-1].block["metadata"]["hitl_request_id"] == ""

    configure_canvas(None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a2ui_tool_preserves_existing_surface_id_when_payload_omits_surface() -> None:
    coordinator = MagicMock()
    coordinator.conversation_id = "conv-a2ui"
    coordinator.prepare_request = AsyncMock(return_value="a2ui-req-3")
    coordinator.wait_for_response = AsyncMock(
        return_value={
            "action_name": "submit",
            "source_component_id": "button-1",
            "context": {"approved": True},
        }
    )
    manager = CanvasManager()
    existing = manager.create_block(
        conversation_id="conv-a2ui",
        block_type="a2ui_surface",
        title="Existing",
        content='{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
        metadata={"surface_id": "surface-1"},
    )
    configure_canvas(manager)
    tool_part = _make_tool_part("call-a2ui", "canvas_create_interactive")

    events = [
        event
        async for event in handle_a2ui_action_tool(
            coordinator=coordinator,
            call_id="call-a2ui",
            tool_name="canvas_create_interactive",
            arguments={
                "title": "Review",
                "components": '{"surfaceUpdate":{"components":[]}}',
                "block_id": existing.id,
            },
            tool_part=tool_part,
        )
    ]

    canvas_event = next(e for e in events if isinstance(e, AgentCanvasUpdatedEvent))
    assert canvas_event.block is not None
    assert canvas_event.block["metadata"]["surface_id"] == "surface-1"

    configure_canvas(None)


class _FailingAttachCoordinator:
    def __init__(self) -> None:
        self.conversation_id = "conv-a2ui"
        self._pending: dict[str, asyncio.Future[object]] = {}

    async def prepare_request(self, *_args, **_kwargs) -> str:
        future: asyncio.Future[object] = asyncio.get_running_loop().create_future()
        self._pending["a2ui-req-4"] = future
        return "a2ui-req-4"

    @property
    def pending_request_ids(self) -> list[str]:
        return list(self._pending.keys())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a2ui_tool_cleans_prepared_request_when_metadata_attach_fails(monkeypatch) -> None:
    coordinator = _FailingAttachCoordinator()
    manager = CanvasManager()
    configure_canvas(manager)
    tool_part = _make_tool_part("call-a2ui", "canvas_create_interactive")
    cancelled_request_ids: list[str] = []

    def _raise_attach(*_args, **_kwargs):
        raise RuntimeError("attach failed")

    class _FakeSession:
        async def commit(self) -> None:
            return None

    class _FakeSessionFactory:
        async def __aenter__(self) -> _FakeSession:
            return _FakeSession()

        async def __aexit__(self, *_args) -> None:
            return None

    class _FakeRepo:
        def __init__(self, _session: _FakeSession) -> None:
            self._session = _session

        async def mark_cancelled(self, request_id: str) -> object:
            cancelled_request_ids.append(request_id)
            return object()

    monkeypatch.setattr(
        "src.infrastructure.agent.processor.hitl_tool_handler._attach_hitl_request_metadata",
        _raise_attach,
    )
    monkeypatch.setattr(
        "src.infrastructure.agent.processor.hitl_tool_handler.async_session_factory",
        _FakeSessionFactory,
    )
    monkeypatch.setattr(
        "src.infrastructure.agent.processor.hitl_tool_handler.SqlHITLRequestRepository",
        _FakeRepo,
    )

    events = [
        event
        async for event in handle_a2ui_action_tool(
            coordinator=coordinator,
            call_id="call-a2ui",
            tool_name="canvas_create_interactive",
            arguments={
                "title": "Review",
                "components": '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
            },
            tool_part=tool_part,
        )
    ]

    observe_event = next(e for e in events if isinstance(e, AgentObserveEvent))
    assert observe_event.error == "attach failed"
    assert coordinator.pending_request_ids == []
    assert cancelled_request_ids == ["a2ui-req-4"]
    assert manager.get_blocks("conv-a2ui") == []

    configure_canvas(None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a2ui_tool_errors_when_reusing_non_a2ui_block() -> None:
    coordinator = MagicMock()
    coordinator.conversation_id = "conv-a2ui"
    manager = CanvasManager()
    existing = manager.create_block(
        conversation_id="conv-a2ui",
        block_type="markdown",
        title="Notes",
        content="# notes",
    )
    configure_canvas(manager)
    tool_part = _make_tool_part("call-a2ui", "canvas_create_interactive")

    events = [
        event
        async for event in handle_a2ui_action_tool(
            coordinator=coordinator,
            call_id="call-a2ui",
            tool_name="canvas_create_interactive",
            arguments={
                "title": "Review",
                "components": '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
                "block_id": existing.id,
            },
            tool_part=tool_part,
        )
    ]

    observe_event = next(e for e in events if isinstance(e, AgentObserveEvent))
    assert "not an A2UI surface" in (observe_event.error or "")

    configure_canvas(None)
