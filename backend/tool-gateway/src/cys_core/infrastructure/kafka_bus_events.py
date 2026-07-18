from __future__ import annotations

import asyncio
import json
from typing import Any

from bootstrap.settings import get_settings, settings
from cys_core.infrastructure.kafka_retry import start_with_retry
from cys_core.infrastructure.kafka_topics import BUS_FINDINGS_TOPIC


async def consume_bus_finding(timeout: float | None = None, *, group_id: str = "bus-findings") -> dict[str, Any] | None:
    """Consume one envelope from bus.findings."""
    resolved_timeout = timeout if timeout is not None else get_settings().kafka_consume_timeout_s
    consumer: Any = None
    try:
        from aiokafka import AIOKafkaConsumer

        async def _build() -> AIOKafkaConsumer:
            built = AIOKafkaConsumer(
                BUS_FINDINGS_TOPIC,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=group_id,
                auto_offset_reset="earliest",
            )
            await built.start()
            return built

        consumer = await start_with_retry(_build, source="kafka_bus_events_consumer")
        record = await asyncio.wait_for(consumer.getone(), timeout=resolved_timeout)
        raw = record.value
        if raw is None:
            return None
        return json.loads(raw.decode())
    except (TimeoutError, Exception):
        return None
    finally:
        if consumer is not None:
            await consumer.stop()
