from __future__ import annotations

from typing import Any

from bootstrap.settings import settings
from cys_core.infrastructure.kafka_publisher import get_kafka_publisher
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
    return await get_kafka_publisher().publish_json(PAUSED_JOBS_TOPIC, record)


def publish_paused_job_sync(record: dict[str, Any]) -> bool:
    _paused_records.append(record)
    if not settings.use_kafka:
        return True
    return get_kafka_publisher().publish_json_sync(PAUSED_JOBS_TOPIC, record)
