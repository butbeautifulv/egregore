from __future__ import annotations

from typing import Any

from bootstrap.settings import Settings, get_settings
from cys_core.infrastructure.kafka_publisher import get_kafka_publisher


async def publish_audit_event(topic: str, record: dict[str, Any], *, settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    if not cfg.use_kafka:
        return True
    publisher = get_kafka_publisher(settings=cfg) if settings is not None else get_kafka_publisher()
    return await publisher.publish_json(topic, record)


def publish_audit_event_sync(topic: str, record: dict[str, Any], *, settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    if not cfg.use_kafka:
        return True
    publisher = get_kafka_publisher(settings=cfg) if settings is not None else get_kafka_publisher()
    return publisher.publish_json_sync(topic, record)
