from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.application.workers.finding_publisher import WorkerFindingPublisher
from cys_core.domain.workers.models import WorkerJob


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finding_publisher_publishes_to_bus_and_transport():
    published: list[dict] = []

    class Bus:
        def send_message(self, sender, recipient, msg_type, payload):
            return {"signature": "sig-1"}

        def receive_message(self, recipient, envelope):
            return None

    transport = SimpleNamespace(publish_delivery=AsyncMock(side_effect=lambda env: published.append(env)))
    publisher = WorkerFindingPublisher(bus=Bus(), transport=transport)
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc", correlation_id="inv-1")
    defn = SimpleNamespace(bus_recipients=["critic"])
    await publisher.publish(
        job=job,
        defn=defn,
        result={"summary": "ok"},
        sandbox_id="sb-1",
        investigation_id="inv-1",
    )
    assert len(published) == 1
    transport.publish_delivery.assert_awaited()


@pytest.mark.unit
def test_finding_publisher_persists_memory():
    stored: list[dict] = []

    class Writer:
        def append_pending_finding(self, **kwargs):
            stored.append(kwargs)
            return SimpleNamespace(memory_type="pending_finding")

    recorded: list[str] = []
    publisher = WorkerFindingPublisher(
        bus=SimpleNamespace(send_message=lambda *a, **k: {}, receive_message=lambda *a, **k: None),
        transport=SimpleNamespace(publish_delivery=AsyncMock()),
        memory_writer=Writer(),
        record_memory_write=lambda tenant, memory_type: recorded.append(memory_type),
    )
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc", correlation_id="inv-1")
    publisher.persist_memory(job=job, result={"summary": "ok"}, investigation_id="inv-1")
    assert stored
    assert recorded == ["pending_finding"]
