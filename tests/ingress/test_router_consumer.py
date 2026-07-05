from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.dispatch_event import DispatchEvent
from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs
from cys_core.domain.events.models import SecurityEvent
from cys_core.application.plans.plan_loader import load_plan_routing
from tests.conftest import make_event_router
from cys_core.infrastructure.queue import InMemoryJobQueue
from interfaces.ingress.router_consumer import RouterConsumer


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
    router = make_event_router([load_plan_routing(plan)])
    queue = InMemoryJobQueue()
    enqueuer = EnqueueWorkerJobs(queue=queue, job_store=MagicMock())
    dispatch = DispatchEvent(router=router, enqueuer=enqueuer)

    async def fake_consume(_timeout: float) -> SecurityEvent:
        return SecurityEvent(id="e1", type="siem.alert", payload={"alert": "x"})

    consumer = RouterConsumer(dispatch=dispatch, consume_raw=fake_consume)
    assert await consumer.process_one() is True
    job = await queue.adequeue()
    assert job is not None
    assert job.persona == "soc"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_router_consumer_idle_when_no_events():
    queue = InMemoryJobQueue()
    enqueuer = EnqueueWorkerJobs(queue=queue, job_store=MagicMock())
    dispatch = DispatchEvent(router=make_event_router([]), enqueuer=enqueuer)

    async def no_events(_timeout: float) -> None:
        return None

    consumer = RouterConsumer(dispatch=dispatch, consume_raw=no_events)
    assert await consumer.process_one() is False
