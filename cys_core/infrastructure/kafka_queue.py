from __future__ import annotations

import json
from typing import Any

from config import settings

TOPIC_PREFIX = "worker.jobs"
DLQ_TOPIC = "worker.jobs.dlq"


class KafkaJobQueue:
    """Kafka-backed job queue (Redpanda-compatible).

    Each daemon instance binds to one consume_topic (e.g. worker.jobs.soc).
    The producer side publishes to worker.jobs.{job['persona']}.
    """

    name = "kafka"

    def __init__(
        self,
        bootstrap_servers: str | None = None,
        consume_topic: str | None = None,
        consumer_group: str | None = None,
    ) -> None:
        self._bootstrap = bootstrap_servers or settings.kafka_bootstrap_servers
        self._consume_topic = consume_topic
        self._group = consumer_group or f"{settings.kafka_consumer_group_prefix}-workers"
        self._fallback_queue: list[dict[str, Any]] = []
        self._available = False
        self._producer: Any = None
        self._consumer: Any = None
        # Lazy-init: actual Kafka connection is established on first use

    def _produce_topic(self, job: dict[str, Any]) -> str:
        persona = job.get("persona", "unknown")
        return f"{TOPIC_PREFIX}.{persona}"

    def _check_aiokafka(self) -> bool:
        try:
            import aiokafka  # noqa: F401
            return True
        except ImportError:
            return False

    def enqueue(self, job: dict[str, Any]) -> str:
        """Sync enqueue — falls back to in-memory if Kafka unavailable."""
        if not self._check_aiokafka():
            self._fallback_queue.append(job)
            return job.get("job_id", "")
        # For sync context, store in fallback (async path is canonical for Kafka)
        self._fallback_queue.append(job)
        return job.get("job_id", "")

    def dequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        if self._fallback_queue:
            return self._fallback_queue.pop(0)
        return None

    async def aenqueue(self, job: dict[str, Any]) -> str:
        """Async publish to worker.jobs.{persona} topic."""
        if not self._check_aiokafka():
            self._fallback_queue.append(job)
            return job.get("job_id", "")
        try:
            from aiokafka import AIOKafkaProducer

            producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap)
            await producer.start()
            try:
                topic = self._produce_topic(job)
                payload = json.dumps(job, ensure_ascii=False).encode()
                await producer.send_and_wait(topic, payload)
            finally:
                await producer.stop()
        except Exception:
            self._fallback_queue.append(job)
        return job.get("job_id", "")

    async def adequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        """Async poll from consume_topic (one message per call)."""
        if self._fallback_queue:
            return self._fallback_queue.pop(0)
        if not self._check_aiokafka() or not self._consume_topic:
            return None
        try:
            from aiokafka import AIOKafkaConsumer

            consumer = AIOKafkaConsumer(
                self._consume_topic,
                bootstrap_servers=self._bootstrap,
                group_id=self._group,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
            )
            await consumer.start()
            try:
                timeout_ms = int(timeout * 1000) if timeout > 0 else 500
                records = await consumer.getmany(timeout_ms=timeout_ms, max_records=1)
                for _tp, msgs in records.items():
                    if msgs:
                        return json.loads(msgs[0].value.decode())
            finally:
                await consumer.stop()
        except Exception:
            pass
        return None
