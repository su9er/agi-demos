from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.infrastructure.adapters.primary.web.routers.agent.messages import (
    _DISPLAYABLE_EVENTS,
    _build_completion_map,
    _build_timeline,
)


@dataclass
class _StubEvent:
    event_type: str
    event_data: dict[str, Any]
    event_time_us: int = 1_000
    event_counter: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    message_id: str = "msg-1"


def test_displayable_events_include_a2ui_action_asked() -> None:
    assert "a2ui_action_asked" in _DISPLAYABLE_EVENTS


def test_build_timeline_includes_a2ui_action_asked() -> None:
    timeline = _build_timeline(
        events=[
            _StubEvent(
                event_type="a2ui_action_asked",
                event_data={
                    "request_id": "hitl-req-1",
                    "block_id": "block-1",
                    "title": "Review",
                    "timeout_seconds": 300,
                },
            )
        ],
        tool_exec_map={},
        hitl_answered_map={},
        hitl_status_map={"hitl-req-1": {"status": "completed"}},
        artifact_ready_map={},
        artifact_error_map={},
        completion_map={},
    )

    assert timeline == [
        {
            "id": "a2ui_action_asked-1000-0",
            "type": "a2ui_action_asked",
            "eventTimeUs": 1_000,
            "eventCounter": 0,
            "timestamp": 1,
            "request_id": "hitl-req-1",
            "block_id": "block-1",
            "title": "Review",
            "timeout_seconds": 300,
            "status": "completed",
            "answered": True,
        }
    ]


def test_build_timeline_preserves_canvas_updated_payload_shape() -> None:
    timeline = _build_timeline(
        events=[
            _StubEvent(
                event_type="canvas_updated",
                event_data={
                    "action": "updated",
                    "block_id": "block-chart-1",
                    "block": {
                        "id": "block-chart-1",
                        "block_type": "chart",
                        "title": "Sales Chart",
                        "content": '{"labels":["Jan"],"datasets":[{"label":"Sales","data":[12]}]}',
                        "metadata": {"mime_type": "application/json"},
                        "version": 2,
                    },
                },
            )
        ],
        tool_exec_map={},
        hitl_answered_map={},
        hitl_status_map={},
        artifact_ready_map={},
        artifact_error_map={},
        completion_map={},
    )

    assert timeline == [
        {
            "id": "canvas_updated-1000-0",
            "type": "canvas_updated",
            "eventTimeUs": 1_000,
            "eventCounter": 0,
            "timestamp": 1,
            "action": "updated",
            "block_id": "block-chart-1",
            "block": {
                "id": "block-chart-1",
                "block_type": "chart",
                "title": "Sales Chart",
                "content": '{"labels":["Jan"],"datasets":[{"label":"Sales","data":[12]}]}',
                "metadata": {"mime_type": "application/json"},
                "version": 2,
            },
        }
    ]


def test_build_timeline_merges_complete_metadata_into_assistant_message() -> None:
    assistant_event = _StubEvent(
        event_type="assistant_message",
        event_data={
            "message_id": "assistant-1",
            "content": "Done",
            "role": "assistant",
        },
        message_id="msg-assistant-1",
    )
    timeline = _build_timeline(
        events=[assistant_event],
        tool_exec_map={},
        hitl_answered_map={},
        hitl_status_map={},
        artifact_ready_map={},
        artifact_error_map={},
        completion_map={
            "assistant_message-1000-0": {
                "trace_url": "https://trace.example/1",
                "execution_summary": {"step_count": 2, "artifact_count": 1},
                "artifacts": [{"url": "https://artifact.example/1"}],
            }
        },
    )

    assert timeline[0]["artifacts"] == [{"url": "https://artifact.example/1"}]
    assert timeline[0]["metadata"] == {
        "traceUrl": "https://trace.example/1",
        "executionSummary": {"step_count": 2, "artifact_count": 1},
    }


def test_build_completion_map_targets_only_last_assistant_message_for_turn() -> None:
    first_assistant = _StubEvent(
        event_type="assistant_message",
        event_data={"content": "First", "role": "assistant"},
        event_time_us=1_000,
        event_counter=0,
        message_id="turn-1",
    )
    second_assistant = _StubEvent(
        event_type="assistant_message",
        event_data={"content": "Final", "role": "assistant"},
        event_time_us=2_000,
        event_counter=0,
        message_id="turn-1",
    )
    completion_map = _build_completion_map(
        {
            "turn-1": [
                first_assistant,
                second_assistant,
                _StubEvent(
                    event_type="complete",
                    event_data={"trace_url": "https://trace.example/2"},
                    event_time_us=3_000,
                    event_counter=0,
                    message_id="turn-1",
                ),
            ]
        }
    )

    timeline = _build_timeline(
        events=[first_assistant, second_assistant],
        tool_exec_map={},
        hitl_answered_map={},
        hitl_status_map={},
        artifact_ready_map={},
        artifact_error_map={},
        completion_map=completion_map,
    )

    assert "metadata" not in timeline[0]
    assert timeline[1]["metadata"] == {"traceUrl": "https://trace.example/2"}


def test_build_timeline_does_not_attach_completion_to_earlier_visible_assistant() -> None:
    first_assistant = _StubEvent(
        event_type="assistant_message",
        event_data={"content": "First", "role": "assistant"},
        event_time_us=1_000,
        event_counter=0,
        message_id="turn-1",
    )
    second_assistant = _StubEvent(
        event_type="assistant_message",
        event_data={"content": "Final", "role": "assistant"},
        event_time_us=2_000,
        event_counter=0,
        message_id="turn-1",
    )
    completion_map = _build_completion_map(
        {
            "turn-1": [
                first_assistant,
                second_assistant,
                _StubEvent(
                    event_type="complete",
                    event_data={"trace_url": "https://trace.example/3"},
                    event_time_us=3_000,
                    event_counter=0,
                    message_id="turn-1",
                ),
            ]
        }
    )

    timeline = _build_timeline(
        events=[first_assistant],
        tool_exec_map={},
        hitl_answered_map={},
        hitl_status_map={},
        artifact_ready_map={},
        artifact_error_map={},
        completion_map=completion_map,
    )

    assert "metadata" not in timeline[0]
