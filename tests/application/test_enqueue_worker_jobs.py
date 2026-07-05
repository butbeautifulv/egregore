from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs
from cys_core.domain.workers.models import WorkerJob


class FakeJobStore:
    def __init__(self) -> None:
        self.pending: list[str] = []

    def upsert_pending(self, job_id, persona, **kwargs):
        self.pending.append(job_id)
        return None


class FakeQueue:
    def __init__(self) -> None:
        self.jobs: list[WorkerJob] = []

    def enqueue(self, job: WorkerJob) -> str:
        self.jobs.append(job)
        return job.job_id

    def enqueue_front(self, job: WorkerJob) -> str:
        self.jobs.insert(0, job)
        return job.job_id

    async def aenqueue(self, job: WorkerJob) -> str:
        self.jobs.append(job)
        return job.job_id

    async def aenqueue_front(self, job: WorkerJob) -> str:
        self.jobs.insert(0, job)
        return job.job_id


@pytest.mark.unit
def test_enqueue_from_routing_sync_registers_pending_and_enqueues():
    store = FakeJobStore()
    queue = FakeQueue()
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
    queue = FakeQueue()
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
    queue = FakeQueue()
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
    queue = FakeQueue()
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
    queue = FakeQueue()
    service = EnqueueWorkerJobs(queue=queue, job_store=store)

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
