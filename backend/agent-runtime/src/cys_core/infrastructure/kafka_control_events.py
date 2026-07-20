from __future__ import annotations

import uuid
from typing import Any, cast

from bootstrap.settings import settings
from cys_core.domain.events.models import SecurityEvent, Severity
from cys_core.infrastructure.kafka_events import publish_raw_event
from cys_core.infrastructure.kafka_publisher import get_kafka_publisher
from cys_core.infrastructure.kafka_topics import AWAITING_APPROVAL_TOPIC, ESCALATION_EVENTS_TOPIC


async def _publish_json(topic: str, payload: dict[str, Any]) -> bool:
    if not settings.use_kafka:
        return True
    return await get_kafka_publisher().publish_json(topic, payload)


def _publish_json_sync(topic: str, payload: dict[str, Any]) -> bool:
    if not settings.use_kafka:
        return True
    return get_kafka_publisher().publish_json_sync(topic, payload)


async def publish_awaiting_approval(payload: dict[str, Any]) -> bool:
    """L2 HITL — human gate before escalation / external notify."""
    record = {
        "id": payload.get("id") or f"await-{uuid.uuid4().hex[:12]}",
        "status": "awaiting_approval",
        **payload,
    }
    return await _publish_json(AWAITING_APPROVAL_TOPIC, record)


async def publish_escalation_event(
    *,
    event_id: str,
    source_persona: str,
    payload: dict[str, Any],
    severity: str = "high",
    correlation_id: str = "",
) -> bool:
    """Critic-approved escalation routed to worker plans."""
    event = SecurityEvent(
        id=event_id or f"esc-{uuid.uuid4().hex[:12]}",
        type="escalation",
        source=f"critic:{source_persona}",
        severity=cast(Severity, severity),
        payload={**payload, "critic_approved": True, "source_persona": source_persona},
        correlation_id=correlation_id,
    )
    if settings.use_kafka:
        published = await _publish_json(ESCALATION_EVENTS_TOPIC, event.model_dump())
        if published:
            return True
    return await publish_raw_event(event)


def publish_escalation_event_sync(**kwargs: Any) -> bool:
    from cys_core.infrastructure.async_boundary import run_sync_from_sync_context

    return run_sync_from_sync_context(lambda: publish_escalation_event(**kwargs))
