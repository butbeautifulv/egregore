from __future__ import annotations

import json
from typing import Any

import structlog

from bootstrap.settings import Settings, get_settings
from cys_core.infrastructure.async_boundary import run_sync_from_sync_context
from cys_core.infrastructure.kafka_errors import KafkaBrokerUnavailableError, KafkaPublishError
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import kafka_produce_headers

logger = structlog.get_logger(__name__)


class KafkaPublisher:
    """Shared async Kafka producer for one-shot event publishers."""

    name = "kafka_publisher"

    def __init__(
        self,
        bootstrap_servers: str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self._settings = cfg
        self._bootstrap = bootstrap_servers or cfg.kafka_bootstrap_servers
        self._producer: Any = None

    async def _ensure_producer(self) -> Any:
        if self._producer is not None:
            return self._producer
        try:
            from aiokafka import AIOKafkaProducer

            producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap)
            await producer.start()
            self._producer = producer
            return producer
        except Exception as exc:
            metrics.record_infrastructure_fallback("kafka_publisher", reason="broker_unavailable")
            logger.warning(
                "kafka_publisher_unavailable",
                bootstrap=self._bootstrap,
                error=str(exc),
                exc_info=True,
            )
            raise KafkaBrokerUnavailableError(str(exc)) from exc

    async def publish_bytes(self, topic: str, payload: bytes) -> bool:
        try:
            producer = await self._ensure_producer()
        except KafkaBrokerUnavailableError:
            return False
        try:
            headers = kafka_produce_headers() or None
            await producer.send_and_wait(topic, payload, headers=headers)
            return True
        except Exception as exc:
            metrics.record_infrastructure_fallback("kafka_publisher", reason="publish_failed")
            logger.warning(
                "kafka_publish_failed",
                topic=topic,
                error=str(exc),
                exc_info=True,
            )
            raise KafkaPublishError(str(exc)) from exc

    async def publish_json(self, topic: str, payload: dict[str, Any]) -> bool:
        from cys_core.observability.tracing import get_correlation_id

        enriched = dict(payload)
        correlation_id = get_correlation_id()
        if correlation_id and "correlation_id" not in enriched:
            enriched["correlation_id"] = correlation_id
        encoded = json.dumps(enriched, ensure_ascii=False).encode()
        return await self.publish_bytes(topic, encoded)

    def publish_bytes_sync(self, topic: str, payload: bytes) -> bool:
        return run_sync_from_sync_context(lambda: self.publish_bytes(topic, payload))

    def publish_json_sync(self, topic: str, payload: dict[str, Any]) -> bool:
        return run_sync_from_sync_context(lambda: self.publish_json(topic, payload))

    async def aclose(self) -> None:
        producer = self._producer
        self._producer = None
        if producer is not None:
            await producer.stop()


_publisher: KafkaPublisher | None = None


def get_kafka_publisher(*, settings: Settings | None = None) -> KafkaPublisher:
    """Return shared Kafka publisher; tests may pass explicit settings."""
    global _publisher
    if settings is not None:
        return KafkaPublisher(settings=settings)
    if _publisher is None:
        _publisher = KafkaPublisher()
    return _publisher


def reset_kafka_publisher_cache() -> None:
    """Clear cached publisher (tests)."""
    global _publisher
    _publisher = None
