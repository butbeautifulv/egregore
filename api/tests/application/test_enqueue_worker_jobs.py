from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs
from tests.application.fakes.job_queue import FakeJobQueue, FakeJobStore


@pytest.mark.unit
def test_enqueue_from_routing_sync_registers_pending_and_enqueues():
    store = FakeJobStore()
    queue = FakeJobQueue()
    service = EnqueueWorkerJobs(queue=queue, job_store=store)

    job_ids = service.enqueue_from_routing_sync(
        "evt-pending",
        ["soc", "network"],
        correlation_id="inv-1",
        sequential=True,
    )

    assert len(job_ids) == 2
    assert store.pending == job_ids
    assert len(queue.jobs) == 2
    assert queue.jobs[1].depends_on_persona == "soc"


@pytest.mark.unit
def test_enqueue_from_routing_sync_pipeline_staged_persists_all_enqueues_first():
    store = FakeJobStore()
    queue = FakeJobQueue()
    service = EnqueueWorkerJobs(queue=queue, job_store=store)

    job_ids = service.enqueue_from_routing_sync(
        "evt-pipeline",
        ["soc", "intel", "hunter"],
        correlation_id="inv-pipeline",
        pipeline_staged=True,
    )

    assert len(job_ids) == 3
    assert store.pending == job_ids
    assert len(queue.jobs) == 1
    assert queue.jobs[0].persona == "soc"
    # pipeline_staged first persona is enqueued at queue head
    assert queue.jobs[0].job_id == job_ids[0]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_from_routing_async_pipeline_staged_persists_all_enqueues_first():
    store = FakeJobStore()
    queue = FakeJobQueue()
    service = EnqueueWorkerJobs(queue=queue, job_store=store)

    job_ids = await service.enqueue_from_routing(
        "evt-pipeline-async",
        ["soc", "intel"],
        correlation_id="inv-pipeline-async",
        pipeline_staged=True,
    )

    assert len(job_ids) == 2
    assert store.pending == job_ids
    assert len(queue.jobs) == 1
    assert queue.jobs[0].persona == "soc"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_from_routing_async_registers_pending_and_enqueues():
    store = FakeJobStore()
    queue = FakeJobQueue()
    service = EnqueueWorkerJobs(queue=queue, job_store=store)

    job_ids = await service.enqueue_from_routing(
        "evt-async",
        ["consultant"],
        correlation_id="inv-2",
    )

    assert job_ids
    assert store.pending == job_ids
    assert len(queue.jobs) == 1
    assert queue.jobs[0].persona == "consultant"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_from_bus_revision_sets_feedback():
    store = FakeJobStore()
    queue = FakeJobQueue()
    bus_guard = MagicMock()
    bus_guard.is_tripped.return_value = False
    bus_guard.should_trip.return_value = None
    bus_guard.revision_cap_exceeded.return_value = False
    service = EnqueueWorkerJobs(queue=queue, job_store=store, bus_guard=bus_guard)

    job_id = await service.enqueue_from_bus(
        {
            "type": "revision",
            "recipient": "soc",
            "feedback": "add more detail",
            "payload": {"event_id": "evt-bus", "correlation_id": "inv-bus"},
        }
    )

    assert job_id in store.pending
    assert queue.jobs[0].feedback == "add more detail"
    assert queue.jobs[0].payload["feedback"] == "add more detail"


_WRAPPED_CORRELATION = (
    'USER_DATA_TO_PROCESS [source=agent_bus]:\n'
    '<untrusted_data source="agent_bus">\n'
    "eng-deadbeefcafe\n"
    "</untrusted_data>"
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_from_bus_normalizes_wrapped_correlation_id():
    from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore

    store = InMemoryJobStore()
    queue = FakeJobQueue()
    bus_guard = MagicMock()
    bus_guard.is_tripped.return_value = False
    bus_guard.should_trip.return_value = None
    bus_guard.revision_cap_exceeded.return_value = False
    service = EnqueueWorkerJobs(queue=queue, job_store=store, bus_guard=bus_guard)

    job_id = await service.enqueue_from_bus(
        {
            "type": "revision",
            "recipient": "soc",
            "payload": {
                "event_id": "evt-bus",
                "correlation_id": _WRAPPED_CORRELATION,
                "tenant_id": "default",
            },
        }
    )

    assert job_id
    assert queue.jobs[0].correlation_id == "eng-deadbeefcafe"
