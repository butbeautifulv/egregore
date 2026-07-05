from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from typing import Any

import structlog

from bootstrap.settings import Settings, get_settings
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.async_boundary import run_sync_from_sync_context
from cys_core.infrastructure.kafka_errors import KafkaBrokerUnavailableError, KafkaMessageDecodeError
from cys_core.infrastructure.kafka_topics import DLQ_TOPIC, WORKER_JOBS_TOPIC
from cys_core.infrastructure.queue import InMemoryJobQueue
from cys_core.observability.metrics import metrics

logger = structlog.get_logger(__name__)

_WORKER_POOL_GROUP = "egregore-workers"


class KafkaJobQueue:
    """Kafka-backed worker job queue with in-memory fallback when broker is unavailable."""

    name = "kafka"

    def __init__(
        self,
        bootstrap_servers: str | None = None,
        persona: str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self._settings = cfg
        self._bootstrap = bootstrap_servers or cfg.kafka_bootstrap_servers
        self._persona = persona
        self._fallback = InMemoryJobQueue()
        self._front_buffer: deque[WorkerJob] = deque()
        self._producer: Any = None
        self._consumer: Any = None
        self._connected = False

    def _topic_for_job(self, _job: WorkerJob) -> str:
        return WORKER_JOBS_TOPIC

    def _record_fallback(self, reason: str) -> None:
        metrics.record_infrastructure_fallback("kafka_queue", reason=reason)

    async def _ensure_producer(self) -> bool:
        if self._producer is not None:
            return self._connected
        try:
            from aiokafka import AIOKafkaProducer

            producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap)
            await producer.start()
            self._producer = producer
            self._connected = True
            return True
        except Exception as exc:
            self._connected = False
            self._record_fallback("broker_unavailable")
            logger.warning(
                "kafka_queue_producer_unavailable",
                bootstrap=self._bootstrap,
                error=str(exc),
                exc_info=True,
            )
            raise KafkaBrokerUnavailableError(str(exc)) from exc

    def _consumer_topics(self) -> list[str]:
        return [WORKER_JOBS_TOPIC]

    def _consumer_group_id(self) -> str:
        return _WORKER_POOL_GROUP

    def _max_poll_interval_ms(self) -> int:
        timeout_s = float(self._settings.worker_job_timeout)
        return max(600_000, int(timeout_s * 1000) + 120_000)

    async def _ensure_consumer(self) -> bool:
        if self._consumer is not None:
            return self._connected
        try:
            await self._ensure_producer()
        except KafkaBrokerUnavailableError:
            return False
        try:
            from aiokafka import AIOKafkaConsumer

            consumer = AIOKafkaConsumer(
                *self._consumer_topics(),
                bootstrap_servers=self._bootstrap,
                group_id=self._consumer_group_id(),
                auto_offset_reset="earliest",
                max_poll_interval_ms=self._max_poll_interval_ms(),
            )
            await consumer.start()
            self._consumer = consumer
            return True
        except Exception as exc:
            self._connected = False
            self._record_fallback("consumer_start_failed")
            logger.warning(
                "kafka_queue_consumer_unavailable",
                bootstrap=self._bootstrap,
                group_id=self._consumer_group_id(),
                error=str(exc),
                exc_info=True,
            )
            return False

    async def aclose(self) -> None:
        consumer = self._consumer
        producer = self._producer
        self._consumer = None
        self._producer = None
        self._connected = False
        if consumer is not None:
            await consumer.stop()
        if producer is not None:
            await producer.stop()

    def enqueue(self, job: WorkerJob) -> str:
        return run_sync_from_sync_context(lambda: self.aenqueue(job))

    def dequeue(self, timeout: float = 0.0) -> WorkerJob | None:
        return run_sync_from_sync_context(lambda: self.adequeue(timeout))

    async def aenqueue(self, job: WorkerJob) -> str:
        job_id = job.job_id
        try:
            if not await self._ensure_producer():
                return await self._fallback.aenqueue(job)
        except KafkaBrokerUnavailableError:
            self._record_fallback("enqueue")
            return await self._fallback.aenqueue(job)
        topic = self._topic_for_job(job)
        payload = json.dumps(job.model_dump(mode="json"), ensure_ascii=False).encode()
        await self._producer.send_and_wait(topic, payload)
        return job_id

    def enqueue_front(self, job: WorkerJob) -> str:
        return run_sync_from_sync_context(lambda: self.aenqueue_front(job))

    async def aenqueue_front(self, job: WorkerJob) -> str:
        self._front_buffer.appendleft(job)
        return job.job_id

    @property
    def active_backend(self) -> str:
        return "kafka" if self._connected else "memory"

    def _matches_persona(self, job: WorkerJob) -> bool:
        if not self._persona:
            return True
        return job.persona == self._persona

    async def _dequeue_one_record(self, wait_for: float) -> WorkerJob | None:
        if not await self._ensure_consumer():
            self._record_fallback("dequeue")
            return await self._fallback.adequeue(wait_for)
        try:
            record = await asyncio.wait_for(self._consumer.getone(), timeout=wait_for)
        except TimeoutError:
            return None
        except Exception as exc:
            self._record_fallback("dequeue_error")
            logger.warning("kafka_queue_dequeue_failed", error=str(exc), exc_info=True)
            return await self._fallback.adequeue(wait_for)
        try:
            return WorkerJob.model_validate(json.loads(record.value.decode()))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            self._record_fallback("decode_error")
            logger.warning(
                "kafka_queue_decode_failed",
                error=str(exc),
                exc_info=True,
            )
            raise KafkaMessageDecodeError(str(exc)) from exc

    async def adequeue(self, timeout: float = 0.0) -> WorkerJob | None:
        if self._front_buffer:
            return self._front_buffer.popleft()
        deadline = time.monotonic() + (timeout if timeout > 0 else 2.0)
        while time.monotonic() < deadline:
            remaining = max(0.05, deadline - time.monotonic())
            try:
                job = await self._dequeue_one_record(remaining)
            except KafkaMessageDecodeError:
                continue
            if job is None:
                return None
            if self._matches_persona(job):
                return job
            await self.aenqueue(job)
        return None

    async def send_to_dlq(self, job: WorkerJob, error: str) -> None:
        payload = json.dumps(
            {"job": job.model_dump(mode="json"), "error": error},
            ensure_ascii=False,
        ).encode()
        try:
            if not await self._ensure_producer():
                return
        except KafkaBrokerUnavailableError:
            self._record_fallback("dlq")
            return
        await self._producer.send_and_wait(DLQ_TOPIC, payload)
