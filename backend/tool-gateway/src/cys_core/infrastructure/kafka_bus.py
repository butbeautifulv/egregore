from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from bootstrap.settings import Settings, get_settings
from cys_core.infrastructure.async_boundary import run_sync_from_sync_context
from cys_core.infrastructure.bus_transport import DELIVERY_TOPIC, InMemoryBusTransport
from cys_core.infrastructure.kafka_errors import KafkaBrokerUnavailableError, KafkaPublishError
from cys_core.infrastructure.kafka_topics import BUS_FINDINGS_TOPIC
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import get_correlation_id, trace_carrier
from cys_core.observability.worker_spans import observability_span

logger = structlog.get_logger(__name__)

BusHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


class KafkaBusTransport:
    """Kafka-backed inter-agent bus transport."""

    name = "kafka"
    requires_mtls = True

    def __init__(
        self,
        bootstrap_servers: str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self._bootstrap = bootstrap_servers or cfg.kafka_bootstrap_servers
        self._fallback = InMemoryBusTransport()
        self._handlers: dict[str, list[BusHandler]] = defaultdict(list)
        self._producer: Any = None
        self._connected = False

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
            metrics.record_infrastructure_fallback("kafka_bus", reason="broker_unavailable")
            logger.warning(
                "kafka_bus_producer_unavailable",
                bootstrap=self._bootstrap,
                error=str(exc),
                exc_info=True,
            )
            raise KafkaBrokerUnavailableError(str(exc)) from exc

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        return run_sync_from_sync_context(lambda: self.send_async(message))

    async def send_async(self, message: dict[str, Any]) -> dict[str, Any]:
        await self.publish(BUS_FINDINGS_TOPIC, message)
        return message

    def subscribe(self, channel: str, handler: BusHandler) -> None:
        self._handlers[channel].append(handler)
        self._fallback.subscribe(channel, handler)

    def _enrich_message(self, channel: str, message: dict[str, Any]) -> dict[str, Any]:
        enriched = {**message, "channel": channel}
        correlation_id = get_correlation_id()
        if correlation_id and "correlation_id" not in enriched:
            enriched["correlation_id"] = correlation_id
        return enriched

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        enriched = self._enrich_message(channel, message)
        try:
            if await self._ensure_producer():
                payload = json.dumps(enriched, ensure_ascii=False).encode()
                try:
                    await self._producer.send_and_wait(BUS_FINDINGS_TOPIC, payload)
                except Exception as exc:
                    metrics.record_infrastructure_fallback("kafka_bus", reason="publish_failed")
                    logger.warning(
                        "kafka_bus_publish_failed",
                        channel=channel,
                        error=str(exc),
                        exc_info=True,
                    )
                    raise KafkaPublishError(str(exc)) from exc
        except KafkaBrokerUnavailableError:
            metrics.record_infrastructure_fallback("kafka_bus", reason="publish_fallback")
        await self._fallback.publish(channel, enriched)

    async def publish_delivery(self, message: dict[str, Any]) -> None:
        stamped = {**message, "_trace_carrier": trace_carrier()}
        with observability_span("bus.publish", channel=DELIVERY_TOPIC):
            try:
                await self.publish(DELIVERY_TOPIC, stamped)
            except (KafkaBrokerUnavailableError, KafkaPublishError):
                await self._fallback.publish_delivery(stamped)

    async def aclose(self) -> None:
        producer = self._producer
        self._producer = None
        self._connected = False
        if producer is not None:
            await producer.stop()
