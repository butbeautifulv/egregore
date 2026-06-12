from __future__ import annotations

import pytest

from cys_core.infrastructure.kafka_queue import KafkaJobQueue
from cys_core.infrastructure.kafka_topics import DLQ_TOPIC, worker_job_topic


@pytest.mark.unit
def test_worker_job_topic_naming():
    assert worker_job_topic("soc") == "worker.jobs.soc"
    assert DLQ_TOPIC == "worker.jobs.dlq"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_queue_fallback_enqueue_dequeue():
    queue = KafkaJobQueue(bootstrap_servers="127.0.0.1:1", persona="soc")
    job = {"job_id": "j1", "persona": "soc", "event_id": "e1"}
    job_id = await queue.aenqueue(job)
    assert job_id == "j1"
    dequeued = await queue.adequeue()
    assert dequeued == job


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_queue_dlq_noop_without_broker():
    queue = KafkaJobQueue(bootstrap_servers="127.0.0.1:1", persona="soc")
    await queue.send_to_dlq({"job_id": "j1"}, "boom")


@pytest.mark.unit
def test_kafka_queue_topic_for_job():
    queue = KafkaJobQueue(bootstrap_servers="127.0.0.1:1")
    assert queue._topic_for_job({"persona": "network"}) == "worker.jobs.network"
