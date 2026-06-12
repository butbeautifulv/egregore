from __future__ import annotations

import pytest

from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.events.plans import load_plan_routing
from cys_core.domain.events.router import EventRouter
from interfaces.ingress.router_consumer import RouterConsumer
from interfaces.worker.orchestrator import WorkerOrchestrator


@pytest.mark.unit
@pytest.mark.asyncio
async def test_router_consumer_routes_and_enqueues(tmp_path):
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        """
id: incident-triage
routing:
  rules:
    - event_types: [siem.alert]
      personas: [soc]
""",
        encoding="utf-8",
    )
    router = EventRouter([load_plan_routing(plan)])
    orch = WorkerOrchestrator(registry=_empty_registry())

    async def fake_consume(_timeout: float) -> SecurityEvent:
        return SecurityEvent(id="e1", type="siem.alert", payload={"alert": "x"})

    consumer = RouterConsumer(router=router, orchestrator=orch, consume_raw=fake_consume)
    assert await consumer.process_one() is True
    job = await orch.queue.adequeue()
    assert job is not None
    assert job["persona"] == "soc"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_router_consumer_idle_when_no_events():
    async def no_events(_timeout: float) -> None:
        return None

    consumer = RouterConsumer(
        orchestrator=WorkerOrchestrator(registry=_empty_registry()),
        consume_raw=no_events,
    )
    assert await consumer.process_one() is False


def _empty_registry():
    from types import SimpleNamespace

    return SimpleNamespace(all=lambda: [], get=lambda n: SimpleNamespace(schema_name=None))
