from __future__ import annotations

import asyncio
import json
from typing import Any

from bootstrap.settings import Settings, get_settings


async def publish_audit_event(topic: str, record: dict[str, Any], *, settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    if not cfg.use_kafka:
        return True
    try:
        from aiokafka import AIOKafkaProducer

        producer = AIOKafkaProducer(bootstrap_servers=cfg.kafka_bootstrap_servers)
        await producer.start()
        try:
            await producer.send_and_wait(topic, json.dumps(record, ensure_ascii=False).encode())
            return True
        finally:
            await producer.stop()
    except Exception:
        return False


def publish_audit_event_sync(topic: str, record: dict[str, Any], *, settings: Settings | None = None) -> bool:
    return asyncio.run(publish_audit_event(topic, record, settings=settings))
