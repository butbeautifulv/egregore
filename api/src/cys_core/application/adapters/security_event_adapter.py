from __future__ import annotations

from cys_core.domain.catalog.profile_id import resolve_profile_id
from cys_core.domain.events.domain_events import DomainEvent, TaskEvent
from cys_core.domain.events.models import SecurityEvent


def security_event_to_domain(event: SecurityEvent, *, domain: str = "cybersecurity") -> DomainEvent:
    profile_id = resolve_profile_id(
        explicit=event.payload.get("profile_id"),
        payload=event.payload,
    )
    task_kind = "investigation"
    if event.type == "manual.consultation":
        task_kind = "consultation"
    elif event.type == "assessment.complete":
        task_kind = "benchmark"
    if event.type.startswith("manual."):
        return TaskEvent(
            id=event.id,
            domain=domain,
            event_type=event.type,
            tenant_id=event.tenant_id,
            correlation_id=event.correlation_id or event.id,
            profile_id=profile_id,
            severity=event.severity,
            payload=dict(event.payload),
            source=event.source,
            task_kind=task_kind,
        )
    return DomainEvent(
        id=event.id,
        domain=domain,
        event_type=event.type,
        tenant_id=event.tenant_id,
        correlation_id=event.correlation_id or event.id,
        profile_id=profile_id,
        severity=event.severity,
        payload=dict(event.payload),
        source=event.source,
    )
