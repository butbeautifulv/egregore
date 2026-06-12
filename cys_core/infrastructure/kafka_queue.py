from __future__ import annotations

import asyncio
import json
from typing import Any

from bootstrap.settings import Settings, get_settings
from cys_core.infrastructure.kafka_topics import DLQ_TOPIC, worker_job_topic
from cys_core.infrastructure.queue import InMemoryJobQueue


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

    async def _ensure_consumer(self) -> bool:
        if self._persona is None:
            return False
        if self._consumer is not None:
            return self._connected
        if not await self._ensure_producer():
            return False
        try:
            from aiokafka import AIOKafkaConsumer

            consumer = AIOKafkaConsumer(
                worker_job_topic(self._persona),
                bootstrap_servers=self._bootstrap,
                group_id=f"workers-{self._persona}",
                auto_offset_reset="earliest",
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
        if self._persona is None:
            return await self._fallback.adequeue(timeout)
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
