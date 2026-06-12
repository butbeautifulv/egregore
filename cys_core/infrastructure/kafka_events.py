from __future__ import annotations

import asyncio
import json
from typing import Any

from bootstrap.settings import settings
from cys_core.domain.events.models import SecurityEvent
from cys_core.infrastructure.kafka_topics import RAW_EVENTS_TOPIC


async def publish_raw_event(event: SecurityEvent) -> bool:
    """Publish a security event to the raw ingress topic."""
    try:
        from aiokafka import AIOKafkaProducer

        producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        await producer.start()
        try:
            await producer.send_and_wait(RAW_EVENTS_TOPIC, event.model_dump_json().encode())
            return True
        finally:
            await producer.stop()
    except Exception:
        return False


def publish_raw_event_sync(event: SecurityEvent) -> bool:
    return asyncio.run(publish_raw_event(event))


async def consume_raw_event(timeout: float = 1.0) -> SecurityEvent | None:
    """Consume one event from the raw ingress topic."""
    consumer: Any = None
    try:
        from aiokafka import AIOKafkaConsumer

        consumer = AIOKafkaConsumer(
            RAW_EVENTS_TOPIC,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id="router-consumer",
            auto_offset_reset="earliest",
        )
        await consumer.start()
        record = await asyncio.wait_for(consumer.getone(), timeout=timeout)
        data = json.loads(record.value.decode())
        return SecurityEvent.model_validate(data)
    except (TimeoutError, Exception):
        return None
    finally:
        if consumer is not None:
            await consumer.stop()
