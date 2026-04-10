"""Unit tests for HITLStreamRouterActor."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.agent.actor import hitl_router_actor
from src.infrastructure.agent.actor.state import snapshot_repo as snapshot_repo_mod
from src.infrastructure.agent.hitl import utils as hitl_utils


class _FakeContinue:
    def __init__(self) -> None:
        self.called_with = None

    def remote(self, request_id, response_data, conversation_id=None, message_id=None):
        self.called_with = (request_id, response_data, conversation_id, message_id)
        return "ref"


class _FakeActor:
    def __init__(self) -> None:
        self.continue_chat = _FakeContinue()


@pytest.mark.unit
class TestHITLStreamRouterActor:
    """Tests for HITLStreamRouterActor."""

    async def test_handle_message_routes_to_actor_and_acks(self, monkeypatch):
        # Get the underlying class from the Ray ActorClass wrapper
        ActorClass = hitl_router_actor.HITLStreamRouterActor
        inner_cls = ActorClass.__ray_metadata__.modified_class
        actor = inner_cls.__new__(inner_cls)
        actor._redis = AsyncMock()
        actor._background_tasks = set()

        fake_actor = _FakeActor()
        get_actor_mock = AsyncMock(return_value=fake_actor)
        monkeypatch.setattr(actor, "_get_or_create_actor", get_actor_mock)
        monkeypatch.setattr(
            hitl_utils,
            "load_persisted_hitl_request",
            AsyncMock(
                return_value=SimpleNamespace(
                    tenant_id="tenant-1",
                    project_id="project-1",
                    conversation_id=None,
                    message_id=None,
                    request_type=SimpleNamespace(value="clarification"),
                    metadata={},
                    status="answered",
                )
            ),
        )
        monkeypatch.setattr(
            snapshot_repo_mod,
            "load_hitl_snapshot_agent_mode",
            AsyncMock(return_value="plan"),
        )

        await_ray_mock = AsyncMock(return_value={"ack": True, "durably_completed": True})
        monkeypatch.setattr(hitl_router_actor, "await_ray", await_ray_mock)

        payload = {
            "request_id": "req-1",
            "response_data": {"answer": "ok"},
            "agent_mode": "default",
            "tenant_id": "tenant-1",
            "project_id": "project-1",
        }

        await actor._handle_message(
            stream_key="hitl:response:tenant-1:project-1",
            msg_id="1-0",
            fields={"data": json.dumps(payload)},
        )
        await asyncio.gather(*list(actor._background_tasks))

        assert fake_actor.continue_chat.called_with == ("req-1", {"answer": "ok"}, None, None)
        await_ray_mock.assert_awaited_once()
        get_actor_mock.assert_awaited_once_with("tenant-1", "project-1", "plan")
        actor._redis.xack.assert_awaited_once_with(
            "hitl:response:tenant-1:project-1",
            actor.CONSUMER_GROUP,
            "1-0",
        )

    async def test_handle_message_leaves_stream_pending_when_actor_not_durable(self, monkeypatch):
        ActorClass = hitl_router_actor.HITLStreamRouterActor
        inner_cls = ActorClass.__ray_metadata__.modified_class
        actor = inner_cls.__new__(inner_cls)
        actor._redis = AsyncMock()
        actor._background_tasks = set()

        fake_actor = _FakeActor()
        monkeypatch.setattr(actor, "_get_or_create_actor", AsyncMock(return_value=fake_actor))
        monkeypatch.setattr(
            hitl_utils,
            "load_persisted_hitl_request",
            AsyncMock(
                return_value=SimpleNamespace(
                    tenant_id="tenant-1",
                    project_id="project-1",
                    conversation_id="conv-db",
                    message_id="msg-db",
                    request_type=SimpleNamespace(value="clarification"),
                    metadata={},
                    status="answered",
                )
            ),
        )
        monkeypatch.setattr(
            snapshot_repo_mod,
            "load_hitl_snapshot_agent_mode",
            AsyncMock(return_value="plan"),
        )
        monkeypatch.setattr(
            hitl_router_actor,
            "await_ray",
            AsyncMock(return_value={"ack": False, "durably_completed": False}),
        )

        await actor._handle_message(
            stream_key="hitl:response:tenant-1:project-1",
            msg_id="1-0",
            fields={
                "data": json.dumps(
                    {
                        "request_id": "req-1",
                        "tenant_id": "tenant-payload",
                        "project_id": "project-payload",
                        "conversation_id": "conv-payload",
                        "message_id": "msg-payload",
                        "hitl_type": "clarification",
                        "response_data": {"answer": "ok"},
                    }
                )
            },
        )
        await asyncio.gather(*list(actor._background_tasks))

        assert fake_actor.continue_chat.called_with == ("req-1", {"answer": "ok"}, "conv-db", "msg-db")
        actor._redis.xack.assert_not_awaited()

    async def test_handle_message_recovers_stale_processing_request(self, monkeypatch):
        ActorClass = hitl_router_actor.HITLStreamRouterActor
        inner_cls = ActorClass.__ray_metadata__.modified_class
        actor = inner_cls.__new__(inner_cls)
        actor._redis = AsyncMock()
        actor._background_tasks = set()

        fake_actor = _FakeActor()
        monkeypatch.setattr(actor, "_get_or_create_actor", AsyncMock(return_value=fake_actor))
        monkeypatch.setattr(actor, "_recover_stale_processing_request", AsyncMock(return_value=True))
        monkeypatch.setattr(
            hitl_utils,
            "load_persisted_hitl_request",
            AsyncMock(
                return_value=SimpleNamespace(
                    tenant_id="tenant-1",
                    project_id="project-1",
                    conversation_id="conv-db",
                    message_id="msg-db",
                    request_type=SimpleNamespace(value="clarification"),
                    metadata={},
                    response_metadata={"processing_heartbeat_at": "2000-01-01T00:00:00+00:00"},
                    status="processing",
                )
            ),
        )
        monkeypatch.setattr(hitl_utils, "is_processing_lease_stale", lambda *_args, **_kwargs: True)
        monkeypatch.setattr(
            snapshot_repo_mod,
            "load_hitl_snapshot_agent_mode",
            AsyncMock(return_value="plan"),
        )
        monkeypatch.setattr(
            hitl_router_actor,
            "await_ray",
            AsyncMock(return_value={"ack": True, "durably_completed": True}),
        )

        await actor._handle_message(
            stream_key="hitl:response:tenant-1:project-1",
            msg_id="1-0",
            fields={"data": json.dumps({"request_id": "req-1", "response_data": {"answer": "ok"}})},
            pending_idle_ms=actor.STALE_PROCESSING_IDLE_MS,
        )
        await asyncio.gather(*list(actor._background_tasks))

        actor._recover_stale_processing_request.assert_awaited_once()
        assert fake_actor.continue_chat.called_with == ("req-1", {"answer": "ok"}, "conv-db", "msg-db")
