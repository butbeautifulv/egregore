from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cys_core.domain.events.models import RoutingDecision, SecurityEvent
from cys_core.domain.events.router import EventRouter
from ingress.router_consumer import RouterConsumer


def make_event(event_type: str = "siem.alert") -> SecurityEvent:
    return SecurityEvent(
        id=f"evt-{uuid.uuid4().hex[:8]}",
        type=event_type,  # type: ignore
        source="test",
        severity="medium",
        payload={"alert": "test"},
    )


def make_router_with_decision(personas: list[str]) -> EventRouter:
    router = MagicMock(spec=EventRouter)
    router.route.return_value = RoutingDecision(
        event_id="test-event-id",
        personas=personas,
        playbook_id="test-plan",
        notify_control=False,
    )
    return router


@pytest.mark.asyncio
async def test_process_message_routes_event():
    event = make_event("siem.alert")
    router = make_router_with_decision(["soc"])

    consumer = RouterConsumer(router=router)
    enqueued: list[dict[str, Any]] = []

    async def fake_aenqueue(job: dict) -> str:
        enqueued.append(job)
        return job["job_id"]

    mock_queue = MagicMock()
    mock_queue.aenqueue = fake_aenqueue

    with patch("ingress.router_consumer.KafkaJobQueue", return_value=mock_queue):
        await consumer._process_message(json.dumps(event.model_dump(), ensure_ascii=False).encode())

    assert len(enqueued) == 1
    assert enqueued[0]["persona"] == "soc"
    assert enqueued[0]["event_id"] == event.id


@pytest.mark.asyncio
async def test_process_message_multi_persona():
    event = make_event("netflow.beacon")
    router = make_router_with_decision(["network", "soc"])

    consumer = RouterConsumer(router=router)
    enqueued: list[dict[str, Any]] = []

    async def fake_aenqueue(job: dict) -> str:
        enqueued.append(job)
        return job["job_id"]

    mock_queue = MagicMock()
    mock_queue.aenqueue = fake_aenqueue

    with patch("ingress.router_consumer.KafkaJobQueue", return_value=mock_queue):
        await consumer._process_message(json.dumps(event.model_dump(), ensure_ascii=False).encode())

    personas = {j["persona"] for j in enqueued}
    assert personas == {"network", "soc"}


@pytest.mark.asyncio
async def test_process_message_invalid_json():
    router = make_router_with_decision(["soc"])
    consumer = RouterConsumer(router=router)
    # Should not raise
    await consumer._process_message(b"not valid json")
    assert consumer._events_routed == 0


@pytest.mark.asyncio
async def test_process_message_no_route():
    # Use a valid event type but router returns no matching personas
    event = make_event("manual.investigation")
    router = make_router_with_decision([])
    consumer = RouterConsumer(router=router)
    await consumer._process_message(json.dumps(event.model_dump(), ensure_ascii=False).encode())
    assert consumer._events_routed == 0


def test_make_job_structure():
    event = make_event("siem.alert")
    router = make_router_with_decision(["soc"])
    consumer = RouterConsumer(router=router)
    job = consumer._make_job(event, "soc", "plan-1")
    assert job["persona"] == "soc"
    assert job["event_id"] == event.id
    assert job["playbook_id"] == "plan-1"
    assert "job_id" in job


@pytest.mark.asyncio
async def test_run_stops_on_stop_event():
    """Consumer stops when stop_event is set."""
    router = make_router_with_decision(["soc"])
    consumer = RouterConsumer(router=router, bootstrap_servers="localhost:9092")

    call_count = 0

    mock_consumer = AsyncMock()

    async def fake_getmany(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            consumer._stop_event.set()
        return {}

    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    mock_consumer.getmany = fake_getmany

    with patch("aiokafka.AIOKafkaConsumer", return_value=mock_consumer):
        count = await consumer.run()

    assert count == 0
    assert call_count >= 2
