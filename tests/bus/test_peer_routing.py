from __future__ import annotations

import pytest

from cys_core.application.bus_ingress_router import BusIngressRouter
from cys_core.infrastructure.engagement.memory_egress import MemoryEngagementEgress
from cys_core.infrastructure.engagement.noop_egress import NoopEngagementEgress


@pytest.mark.asyncio
async def test_bus_router_enqueues_worker_job():
    enqueued: list[dict] = []

    def _enqueue(envelope: dict) -> str:
        enqueued.append(envelope)
        return "job-1"

    router = BusIngressRouter(orchestration_enqueue=_enqueue)
    await router.route_envelope(
        {
            "recipient": "network",
            "type": "finding",
            "payload": {"event_id": "e1", "correlation_id": "eng-1"},
            "signature": "sig-1",
        }
    )
    assert len(enqueued) == 1
    assert enqueued[0]["recipient"] == "network"


@pytest.mark.asyncio
async def test_bus_router_idempotent():
    calls = 0

    def _enqueue(_envelope: dict) -> str:
        nonlocal calls
        calls += 1
        return "job-1"

    router = BusIngressRouter(orchestration_enqueue=_enqueue)
    envelope = {"recipient": "network", "type": "delegate", "signature": "dup"}
    await router.route_envelope(envelope)
    await router.route_envelope(envelope)
    assert calls == 1


@pytest.mark.asyncio
async def test_memory_egress_subscribe_receives_publish():
    egress = MemoryEngagementEgress()
    egress.publish_event("eng-1", "status", {"tenant_id": "default", "phase": "running"})
    events = egress.snapshot("eng-1")
    assert len(events) == 1
    assert events[0]["type"] == "status"


def test_noop_egress_does_not_raise():
    egress = NoopEngagementEgress()
    egress.publish_status("eng-1", "created", {})
    egress.publish_event("eng-1", "control", {})
