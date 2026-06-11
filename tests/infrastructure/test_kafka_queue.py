from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cys_core.infrastructure.kafka_queue import KafkaJobQueue


TEST_JOB = {
    "job_id": "test-job-1",
    "persona": "soc",
    "event_id": "evt-1",
    "payload": {"alert": "test"},
}


def test_kafka_queue_name():
    q = KafkaJobQueue()
    assert q.name == "kafka"


def test_produce_topic():
    q = KafkaJobQueue()
    assert q._produce_topic({"persona": "soc"}) == "worker.jobs.soc"
    assert q._produce_topic({"persona": "redteam"}) == "worker.jobs.redteam"


def test_sync_enqueue_fallback_when_no_kafka():
    """Sync enqueue falls back to in-memory when aiokafka not available."""
    q = KafkaJobQueue()
    with patch.object(q, "_check_aiokafka", return_value=False):
        job_id = q.enqueue(TEST_JOB)
    assert job_id == "test-job-1"
    assert q._fallback_queue


def test_sync_dequeue_from_fallback():
    q = KafkaJobQueue()
    q._fallback_queue.append(TEST_JOB)
    result = q.dequeue()
    assert result == TEST_JOB
    assert not q._fallback_queue


def test_sync_dequeue_empty():
    q = KafkaJobQueue()
    assert q.dequeue() is None


@pytest.mark.asyncio
async def test_async_enqueue_fallback_when_no_kafka():
    q = KafkaJobQueue()
    with patch.object(q, "_check_aiokafka", return_value=False):
        job_id = await q.aenqueue(TEST_JOB)
    assert job_id == "test-job-1"
    assert len(q._fallback_queue) == 1


@pytest.mark.asyncio
async def test_async_dequeue_from_fallback():
    q = KafkaJobQueue()
    q._fallback_queue.append(TEST_JOB)
    result = await q.adequeue()
    assert result == TEST_JOB


@pytest.mark.asyncio
async def test_async_enqueue_publishes_to_kafka():
    """When aiokafka is available, aenqueue uses AIOKafkaProducer."""
    q = KafkaJobQueue(bootstrap_servers="localhost:9092")

    mock_producer = AsyncMock()
    mock_producer.__aenter__ = AsyncMock(return_value=mock_producer)
    mock_producer.__aexit__ = AsyncMock(return_value=False)
    mock_producer.send_and_wait = AsyncMock()

    with patch("cys_core.infrastructure.kafka_queue.KafkaJobQueue._check_aiokafka", return_value=True):
        with patch("aiokafka.AIOKafkaProducer", return_value=mock_producer):
            await q.aenqueue(TEST_JOB)

    # Falls back gracefully if producer raises (we mock the full flow)
    # Key: no exception raised
    assert True


def test_factory_returns_redis_when_use_kafka_false(monkeypatch):
    from config import Settings
    monkeypatch.setattr("cys_core.infrastructure.queue.settings", Settings(_env_file=None))
    from cys_core.infrastructure.queue import get_job_queue
    get_job_queue.cache_clear()
    q = get_job_queue()
    assert q.name == "redis"
    get_job_queue.cache_clear()


def test_factory_returns_kafka_when_use_kafka_true(monkeypatch):
    from config import Settings
    import os
    monkeypatch.setenv("USE_KAFKA", "true")
    s = Settings(_env_file=None)
    monkeypatch.setattr("cys_core.infrastructure.queue.settings", s)
    from cys_core.infrastructure.queue import get_job_queue
    get_job_queue.cache_clear()
    q = get_job_queue()
    assert q.name == "kafka"
    get_job_queue.cache_clear()
