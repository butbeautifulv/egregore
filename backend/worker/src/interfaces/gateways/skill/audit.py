from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bootstrap.settings import get_settings
from cys_core.infrastructure.kafka_audit import publish_audit_event_sync
from cys_core.infrastructure.kafka_topics import AUDIT_SKILL_LOADS_TOPIC

_audit_records: list[dict[str, Any]] = []


def get_skill_audit_records() -> list[dict[str, Any]]:
    return list(_audit_records)


def clear_skill_audit_records() -> None:
    _audit_records.clear()


def publish_skill_load_sync(record: dict[str, Any]) -> bool:
    return publish_audit_event_sync(AUDIT_SKILL_LOADS_TOPIC, record, settings=get_settings())


def record_skill_load(
    *,
    skill_name: str,
    persona: str,
    content_hash: str,
    job_id: str = "",
    trust_tier: str = "builtin",
) -> None:
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "skill": skill_name,
        "persona": persona,
        "hash": content_hash,
        "job_id": job_id,
        "trust_tier": trust_tier,
    }
    _audit_records.append(record)
    if get_settings().use_kafka:
        publish_skill_load_sync(record)
