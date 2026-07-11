from __future__ import annotations

import asyncio
import json
from typing import Any

from bootstrap.settings import settings
from cys_core.infrastructure.kafka_topics import BUS_FINDINGS_TOPIC


async def consume_bus_finding(timeout: float = 1.0, *, group_id: str = "bus-findings") -> dict[str, Any] | None:
    """Consume one envelope from bus.findings."""
    consumer: Any = None
    try:
        from aiokafka import AIOKafkaConsumer

        consumer = AIOKafkaConsumer(
            BUS_FINDINGS_TOPIC,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=group_id,
            auto_offset_reset="earliest",
        )
        await consumer.start()
        record = await asyncio.wait_for(consumer.getone(), timeout=timeout)
        raw = record.value
        if raw is None:
            return None
        return json.loads(raw.decode())
    except (TimeoutError, Exception):
        return None
    finally:
        if consumer is not None:
            await consumer.stop()
