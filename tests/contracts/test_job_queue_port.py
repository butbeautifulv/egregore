from __future__ import annotations

import pytest

from cys_core.application.ports import JobQueueConnector
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.queue import InMemoryJobQueue, RedisJobQueue


def _job(job_id: str, persona: str = "soc") -> WorkerJob:
    return WorkerJob(job_id=job_id, event_id="evt-1", persona=persona)


@pytest.mark.unit
def test_memory_queue_conforms_to_port():
    queue: JobQueueConnector = InMemoryJobQueue()
    job_id = queue.enqueue(_job("j1"))
    assert job_id == "j1"
    item = queue.dequeue()
    assert item is not None
    assert item.job_id == "j1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_queue_async_conforms_to_port():
    queue: JobQueueConnector = InMemoryJobQueue()
    job_id = await queue.aenqueue(_job("j2"))
    assert job_id == "j2"
    item = await queue.adequeue()
    assert item is not None


@pytest.mark.unit
def test_redis_queue_falls_back_to_memory():
    queue = RedisJobQueue(redis_url="redis://invalid:1/0")
    assert queue.name == "redis"
    job_id = queue.enqueue(_job("j3"))
    assert job_id == "j3"
