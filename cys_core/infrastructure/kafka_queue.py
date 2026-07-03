from __future__ import annotations

import asyncio
import json
from typing import Any

from bootstrap.settings import Settings, get_settings
from cys_core.infrastructure.kafka_topics import DLQ_TOPIC, worker_job_topic
from cys_core.infrastructure.queue import InMemoryJobQueue

_WORKER_POOL_GROUP = "egregore-workers"


def _worker_job_topics() -> list[str]:
    from cys_core.application.resource_source import get_resource_source

    personas = get_resource_source().list_worker_personas()
    if not personas:
        return [worker_job_topic("consultant")]
    return [worker_job_topic(persona) for persona in personas]


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
        self._bootstrap = bootstrap_servers or cfg.kafka_bootstrap_servers
        self._persona = persona
        self._fallback = InMemoryJobQueue()
        self._producer: Any = None
        self._consumer: Any = None
        self._connected = False

    def _topic_for_job(self, job: dict[str, Any]) -> str:
        return worker_job_topic(str(job.get("persona", "default")))

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
        except Exception:
            self._connected = False
            return False

    def _consumer_topics(self) -> list[str]:
        if self._persona:
            return [worker_job_topic(self._persona)]
        return _worker_job_topics()

    def _consumer_group_id(self) -> str:
        if self._persona:
            return f"workers-{self._persona}"
        return _WORKER_POOL_GROUP

    async def _ensure_consumer(self) -> bool:
        if self._consumer is not None:
            return self._connected
        if not await self._ensure_producer():
            return False
        try:
            from aiokafka import AIOKafkaConsumer

            # Job processing blocks poll(); interval must exceed worker_job_timeout (default 180s).
            max_poll_ms = max(600_000, int(cfg.worker_job_timeout * 1000) + 120_000)
            consumer = AIOKafkaConsumer(
                *self._consumer_topics(),
                bootstrap_servers=self._bootstrap,
                group_id=self._consumer_group_id(),
                auto_offset_reset="earliest",
                max_poll_interval_ms=max_poll_ms,
            )
            await consumer.start()
            self._consumer = consumer
            return True
        except Exception:
            self._connected = False
            return False

    def enqueue(self, job: dict[str, Any]) -> str:
        return asyncio.run(self.aenqueue(job))

    def dequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        return asyncio.run(self.adequeue(timeout))

    async def aenqueue(self, job: dict[str, Any]) -> str:
        job_id = job.get("job_id", "")
        if not await self._ensure_producer():
            return await self._fallback.aenqueue(job)
        topic = self._topic_for_job(job)
        payload = json.dumps(job, ensure_ascii=False).encode()
        await self._producer.send_and_wait(topic, payload)
        return job_id

    async def adequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        if not await self._ensure_consumer():
            return await self._fallback.adequeue(timeout)
        try:
            wait_for = timeout if timeout > 0 else 1.0
            record = await asyncio.wait_for(self._consumer.getone(), timeout=wait_for)
            return json.loads(record.value.decode())
        except TimeoutError:
            return None
        except Exception:
            return await self._fallback.adequeue(timeout)

    async def send_to_dlq(self, job: dict[str, Any], error: str) -> None:
        payload = json.dumps({"job": job, "error": error}, ensure_ascii=False).encode()
        if not await self._ensure_producer():
            return
        await self._producer.send_and_wait(DLQ_TOPIC, payload)
