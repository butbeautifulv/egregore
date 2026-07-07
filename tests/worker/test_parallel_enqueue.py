from __future__ import annotations

import pytest

from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs
from cys_core.infrastructure.queue import InMemoryJobQueue


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parallel_enqueue_enqueues_all_jobs_immediately() -> None:
    queue = InMemoryJobQueue()
    enqueuer = EnqueueWorkerJobs(queue=queue, job_store=_NoopJobStore())

    job_ids = await enqueuer.enqueue_from_routing(
        "evt-parallel",
        ["soc", "intel", "hunter"],
        payload={"execution_mode": "parallel", "phase": "specialist"},
        correlation_id="eng-parallel",
        pipeline_staged=False,
    )

    assert len(job_ids) == 3
    assert len(queue._queue) == 3
    personas = {job.persona for job in queue._queue}
    assert personas == {"soc", "intel", "hunter"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_staged_enqueue_defers_follow_up_jobs() -> None:
    queue = InMemoryJobQueue()
    enqueuer = EnqueueWorkerJobs(queue=queue, job_store=_NoopJobStore())

    job_ids = await enqueuer.enqueue_from_routing(
        "evt-staged",
        ["soc", "intel"],
        payload={"execution_mode": "staged", "phase": "specialist"},
        correlation_id="eng-staged",
        pipeline_staged=True,
    )

    assert len(job_ids) == 2
    assert len(queue._queue) == 1
    assert queue._queue[0].persona == "soc"


class _NoopJobStore:
    def upsert_pending(self, *args, **kwargs) -> None:
        pass
