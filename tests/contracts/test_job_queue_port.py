from __future__ import annotations

import pytest

from cys_core.application.ports import JobQueueConnector
from cys_core.infrastructure.queue import InMemoryJobQueue, RedisJobQueue


@pytest.mark.unit
def test_memory_queue_conforms_to_port():
    queue: JobQueueConnector = InMemoryJobQueue()
    job_id = queue.enqueue({"job_id": "j1", "persona": "soc"})
    assert job_id == "j1"
    item = queue.dequeue()
    assert item is not None
    assert item["job_id"] == "j1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_queue_async_conforms_to_port():
    queue: JobQueueConnector = InMemoryJobQueue()
    job_id = await queue.aenqueue({"job_id": "j2", "persona": "soc"})
    assert job_id == "j2"
    item = await queue.adequeue()
    assert item is not None


@pytest.mark.unit
def test_redis_queue_falls_back_to_memory():
    queue = RedisJobQueue(redis_url="redis://invalid:1/0")
    assert queue.name == "redis"
    job_id = queue.enqueue({"job_id": "j3", "persona": "soc"})
    assert job_id == "j3"
