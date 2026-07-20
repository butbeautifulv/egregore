from __future__ import annotations

import pytest

from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.bus_transport import InMemoryBusTransport
from cys_core.infrastructure.queue import InMemoryJobQueue
from cys_core.infrastructure.sandbox import LocalSandboxConnector


@pytest.mark.unit
def test_local_sandbox_lifecycle():
    sb = LocalSandboxConnector()
    creds = sb.create("run-1", "soc")
    assert sb.is_active("run-1")
    assert creds.sandbox_id.startswith("local-run-1")
    sb.destroy("run-1")
    assert not sb.is_active("run-1")


@pytest.mark.unit
def test_in_memory_job_queue():
    q = InMemoryJobQueue()
    q.enqueue(WorkerJob(job_id="j1", event_id="e-1", persona="soc"))
    job = q.dequeue()
    assert job is not None
    assert job.job_id == "j1"
    assert q.dequeue() is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_in_memory_bus_transport():
    bus = InMemoryBusTransport()
    received: list[dict] = []

    async def handler(msg: dict) -> None:
        received.append(msg)

    bus.subscribe("critic", handler)
    await bus.publish("critic", {"sender": "soc", "type": "finding"})
    assert len(received) == 1
