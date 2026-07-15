from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.kafka_errors import (
    KafkaMessageDecodeError,
    KafkaPublishError,
)
from cys_core.infrastructure.kafka_queue import KafkaJobQueue
from interfaces.api.task_supervisor import BackgroundTaskSupervisor


@pytest.mark.unit
def test_kafka_message_decode_error_is_typed() -> None:
    err = KafkaMessageDecodeError("bad json")
    assert str(err) == "bad json"
    assert issubclass(KafkaMessageDecodeError, Exception)


@pytest.mark.unit
def test_kafka_publish_error_is_typed() -> None:
    err = KafkaPublishError("send failed")
    assert str(err) == "send failed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_publisher_raises_on_send_failure() -> None:
    from cys_core.infrastructure.kafka_publisher import KafkaPublisher

    publisher = KafkaPublisher(bootstrap_servers="localhost:19092")
    mock_producer = AsyncMock()
    mock_producer.send_and_wait.side_effect = RuntimeError("broker down")
    with patch.object(publisher, "_ensure_producer", return_value=mock_producer):
        with pytest.raises(KafkaPublishError, match="broker down"):
            await publisher.publish_bytes("worker.jobs", b"{}")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_queue_skips_invalid_payload_and_continues() -> None:
    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092")
    seen = 0

    async def _dequeue_one(_wait: float) -> WorkerJob | None:
        nonlocal seen
        seen += 1
        if seen == 1:
            raise KafkaMessageDecodeError("bad payload")
        return None

    with patch.object(queue, "_dequeue_one_record", side_effect=_dequeue_one):
        job = await queue.adequeue(timeout=0.2)

    assert job is None
    assert seen >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_queue_decode_error_retries_within_timeout() -> None:
    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092")
    valid = WorkerJob(job_id="j-ok", event_id="e-1", persona="consultant")

    async def _dequeue_one(_wait: float) -> WorkerJob | None:
        if not hasattr(_dequeue_one, "called"):
            _dequeue_one.called = True  # type: ignore[attr-defined]
            raise KafkaMessageDecodeError("bad payload")
        return valid

    with patch.object(queue, "_dequeue_one_record", side_effect=_dequeue_one):
        job = await queue.adequeue(timeout=1.0)

    assert job is not None
    assert job.job_id == "j-ok"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_task_supervisor_shutdown_cancels_spawned_tasks() -> None:
    supervisor = BackgroundTaskSupervisor()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _long_task() -> None:
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    supervisor.spawn(_long_task(), name="planner-test")
    await asyncio.wait_for(started.wait(), timeout=1.0)
    await supervisor.shutdown()
    await asyncio.wait_for(cancelled.wait(), timeout=1.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_task_supervisor_logs_task_exception() -> None:
    supervisor = BackgroundTaskSupervisor()

    async def _failing_task() -> None:
        raise RuntimeError("planner boom")

    with patch("interfaces.api.task_supervisor.logger") as mock_logger:
        task = supervisor.spawn(_failing_task(), name="failing-planner")
        with pytest.raises(RuntimeError, match="planner boom"):
            await task
        await asyncio.sleep(0.05)
        mock_logger.error.assert_called()
