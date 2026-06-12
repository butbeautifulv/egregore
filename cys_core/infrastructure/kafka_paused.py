from __future__ import annotations

import asyncio
import json
from typing import Any

from bootstrap.settings import settings
from cys_core.infrastructure.kafka_topics import PAUSED_JOBS_TOPIC

_paused_records: list[dict[str, Any]] = []


def get_paused_records() -> list[dict[str, Any]]:
    return list(_paused_records)


def clear_paused_records() -> None:
    _paused_records.clear()


async def publish_paused_job(record: dict[str, Any]) -> bool:
    _paused_records.append(record)
    if not settings.use_kafka:
        return True
    try:
        from aiokafka import AIOKafkaProducer

        producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        await producer.start()
        try:
            await producer.send_and_wait(PAUSED_JOBS_TOPIC, json.dumps(record, ensure_ascii=False).encode())
            return True
        finally:
            await producer.stop()
    except Exception:
        return False


def publish_paused_job_sync(record: dict[str, Any]) -> bool:
    return asyncio.run(publish_paused_job(record))
