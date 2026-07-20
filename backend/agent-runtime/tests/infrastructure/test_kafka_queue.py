from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.kafka_errors import KafkaBrokerUnavailableError
from cys_core.infrastructure.kafka_queue import KafkaJobQueue
from cys_core.infrastructure.kafka_topics import WORKER_JOBS_TOPIC


def _job(**kwargs: object) -> WorkerJob:
    return WorkerJob(
        job_id=str(kwargs.get("job_id", "j-1")),
        event_id=str(kwargs.get("event_id", "e-1")),
        persona=str(kwargs.get("persona", "consultant")),
    )


@pytest.mark.unit
def test_kafka_queue_uses_single_worker_jobs_topic() -> None:
    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092")
    assert queue._topic_for_job(_job(persona="soc")) == WORKER_JOBS_TOPIC
    assert queue._consumer_topics() == [WORKER_JOBS_TOPIC]
    assert queue._consumer_group_id() == "egregore-workers"


@pytest.mark.unit
def test_kafka_queue_persona_scoped_still_single_topic() -> None:
    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092")
    assert queue._consumer_topics() == [WORKER_JOBS_TOPIC]
    assert queue._consumer_group_id() == "egregore-workers"


@pytest.mark.unit
def test_kafka_queue_max_poll_interval_uses_settings_timeout() -> None:
    from bootstrap.settings import Settings

    settings = Settings(worker_job_timeout=240.0)
    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092", settings=settings)
    assert queue._max_poll_interval_ms() == 600_000


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_queue_aclose_stops_clients() -> None:
    producer = AsyncMock()
    consumer = AsyncMock()
    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092")
    queue._producer = producer
    queue._consumer = consumer
    queue._connected = True

    await queue.aclose()

    consumer.stop.assert_awaited_once()
    producer.stop.assert_awaited_once()
    assert queue._producer is None
    assert queue._consumer is None
    assert queue._connected is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_queue_enqueue_falls_back_when_broker_unavailable() -> None:
    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092")
    with patch.object(queue, "_ensure_producer", side_effect=KafkaBrokerUnavailableError("down")):
        job_id = await queue.aenqueue(_job(job_id="j-1", persona="consultant"))
    assert job_id == "j-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_queue_enqueue_front_publishes_to_broker() -> None:
    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092")
    job = _job(job_id="j-front", persona="soc")
    with patch.object(queue, "aenqueue", new_callable=AsyncMock, return_value="j-front") as mock_enqueue:
        job_id = await queue.aenqueue_front(job)
    mock_enqueue.assert_awaited_once_with(job)
    assert job_id == "j-front"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_queue_persona_filter_requeues_other_persona_jobs() -> None:
    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092")
    calls = iter(
        [
            _job(job_id="j-soc", persona="soc"),
            _job(job_id="j-consultant", persona="consultant"),
        ]
    )

    async def _dequeue_one(_wait: float) -> WorkerJob | None:
        try:
            return next(calls)
        except StopIteration:
            return None

    requeued: list[WorkerJob] = []

    async def _capture_enqueue(job: WorkerJob) -> str:
        requeued.append(job)
        return job.job_id

    from cys_core.observability.metrics import metrics

    before = metrics.job_queue_persona_requeued.labels(persona="soc")._value.get()
    with patch.object(queue, "_dequeue_one_record", side_effect=_dequeue_one):
        with patch.object(queue, "aenqueue", side_effect=_capture_enqueue):
            job = await queue.adequeue(timeout=1.0)
    after = metrics.job_queue_persona_requeued.labels(persona="soc")._value.get()

    assert job is not None
    assert job.job_id == "j-consultant"
    assert len(requeued) == 1
    assert requeued[0].job_id == "j-soc"
    assert after == before + 1


@pytest.mark.asyncio
async def test_kafka_queue_catchall_worker_consumes_planner_job() -> None:
    """A worker started with no --persona (empty string, e.g. scripts/dev.sh's and
    deploy/docker-compose.dev.yml's default) must consume a WorkerJob(persona="planner")
    without requeuing it — this is the deployment invariant documented in AGENTS.md
    and docs/MSP_BACKLOG.md §16 that api's StartEngagement enqueue path
    (task #56/#57) depends on. persona="" here, not a truthy scoped value.
    """
    queue = KafkaJobQueue(persona="", bootstrap_servers="localhost:19092")
    planner_job = _job(job_id="j-planner", persona="planner")

    async def _dequeue_one(_wait: float) -> WorkerJob | None:
        return planner_job

    requeued: list[WorkerJob] = []

    async def _capture_enqueue(job: WorkerJob) -> str:
        requeued.append(job)
        return job.job_id

    with patch.object(queue, "_dequeue_one_record", side_effect=_dequeue_one):
        with patch.object(queue, "aenqueue", side_effect=_capture_enqueue):
            job = await queue.adequeue(timeout=1.0)

    assert job is not None
    assert job.job_id == "j-planner"
    assert requeued == []
