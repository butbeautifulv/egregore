from __future__ import annotations

from typing import Any

from bootstrap.container import get_container
from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.domain.events.models import RoutingDecision, SecurityEvent


class EventIngress:
    """Accept structured events, route to workers, enqueue jobs."""

    def __init__(self, route_and_enqueue: RouteAndEnqueueEvent) -> None:
        self._route_and_enqueue = route_and_enqueue

    def ingest(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        severity: str = "medium",
        source: str = "",
        event_id: str | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
    ) -> tuple[SecurityEvent, RoutingDecision, list[str]]:
        return self._route_and_enqueue.execute(
            event_type,
            payload,
            severity=severity,
            source=source,
            event_id=event_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
        )

    async def aingest(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        severity: str = "medium",
        source: str = "",
        event_id: str | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
    ) -> tuple[SecurityEvent, RoutingDecision, list[str]]:
        return await self._route_and_enqueue.aexecute(
            event_type,
            payload,
            severity=severity,
            source=source,
            event_id=event_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
        )


def get_event_ingress() -> EventIngress:
    return get_container().get_event_ingress()
