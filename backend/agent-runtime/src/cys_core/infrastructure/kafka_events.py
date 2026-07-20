from __future__ import annotations

import asyncio
import json
from typing import Any

from bootstrap.settings import get_settings, settings
from cys_core.domain.events.models import SecurityEvent
from cys_core.infrastructure.kafka_publisher import get_kafka_publisher
from cys_core.infrastructure.kafka_retry import start_with_retry
from cys_core.infrastructure.kafka_topics import RAW_EVENTS_TOPIC
from cys_core.observability.tracing import bind_from_carrier


async def publish_raw_event(event: SecurityEvent) -> bool:
    """Publish a security event to the raw ingress topic."""
    if not settings.use_kafka:
        return True
    return await get_kafka_publisher().publish_bytes(RAW_EVENTS_TOPIC, event.model_dump_json().encode())


def publish_raw_event_sync(event: SecurityEvent) -> bool:
    if not settings.use_kafka:
        return True
    return get_kafka_publisher().publish_bytes_sync(RAW_EVENTS_TOPIC, event.model_dump_json().encode())


async def consume_raw_event(timeout: float | None = None) -> SecurityEvent | None:
    """Consume one event from the raw ingress topic."""
    resolved_timeout = timeout if timeout is not None else get_settings().kafka_consume_timeout_s
    consumer: Any = None
    try:
        from aiokafka import AIOKafkaConsumer

        async def _build() -> AIOKafkaConsumer:
            built = AIOKafkaConsumer(
                RAW_EVENTS_TOPIC,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id="router-consumer",
                auto_offset_reset="earliest",
            )
            await built.start()
            return built

        consumer = await start_with_retry(_build, source="kafka_events_consumer")
        record = await asyncio.wait_for(consumer.getone(), timeout=resolved_timeout)
        if record.headers:
            header_map = {
                key: value.decode("utf-8") if isinstance(value, bytes) else str(value)
                for key, value in record.headers
            }
            bind_from_carrier(header_map)
        raw = record.value
        if raw is None:
            return None
        data = json.loads(raw.decode()) if record.value is not None else {}
        return SecurityEvent.model_validate(data)
    except (TimeoutError, Exception):
        return None
    finally:
        if consumer is not None:
            await consumer.stop()
