from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from bootstrap.settings import Settings, get_settings
from cys_core.infrastructure.bus_transport import InMemoryBusTransport
from cys_core.infrastructure.kafka_topics import BUS_FINDINGS_TOPIC

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
        except Exception:
            self._connected = False
            return False

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        asyncio.run(self.publish(BUS_FINDINGS_TOPIC, message))
        return message

    async def send_async(self, message: dict[str, Any]) -> dict[str, Any]:
        await self.publish(BUS_FINDINGS_TOPIC, message)
        return message

    def subscribe(self, channel: str, handler: BusHandler) -> None:
        self._handlers[channel].append(handler)
        self._fallback.subscribe(channel, handler)

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        enriched = {**message, "channel": channel}
        if await self._ensure_producer():
            payload = json.dumps(enriched, ensure_ascii=False).encode()
            await self._producer.send_and_wait(BUS_FINDINGS_TOPIC, payload)
        await self._fallback.publish(channel, enriched)
