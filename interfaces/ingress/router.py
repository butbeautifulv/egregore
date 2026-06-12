from __future__ import annotations

from functools import lru_cache
from typing import Any

from bootstrap.settings import settings
from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.domain.events.models import RoutingDecision, SecurityEvent
from cys_core.domain.events.router import EventRouter
from cys_core.infrastructure.kafka_events import publish_raw_event, publish_raw_event_sync
from cys_core.observability.metrics import metrics
from cys_core.registry.product_context import default_agents_root
from interfaces.worker.orchestrator import WorkerOrchestrator


class EventIngress:
    """Accept structured events, route to workers, enqueue jobs."""

    def __init__(
        self,
        router: EventRouter | None = None,
        orchestrator: WorkerOrchestrator | None = None,
    ) -> None:
        self.router = router or EventRouter.from_plans_dir(default_agents_root() / "plans")
        self.orchestrator = orchestrator or WorkerOrchestrator()
        self._route_and_enqueue = RouteAndEnqueueEvent(
            router=self.router,
            enqueuer=self.orchestrator,
            use_kafka=settings.use_kafka,
            publish_raw_event_sync=publish_raw_event_sync,
            publish_raw_event=publish_raw_event,
            record_event_ingested=metrics.record_event_ingested,
        )

    def ingest(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        severity: str = "medium",
        source: str = "",
        event_id: str | None = None,
        correlation_id: str = "",
    ) -> tuple[SecurityEvent, RoutingDecision, list[str]]:
        return self._route_and_enqueue.execute(
            event_type,
            payload,
            severity=severity,
            source=source,
            event_id=event_id,
            correlation_id=correlation_id,
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
    ) -> tuple[SecurityEvent, RoutingDecision, list[str]]:
        return await self._route_and_enqueue.aexecute(
            event_type,
            payload,
            severity=severity,
            source=source,
            event_id=event_id,
            correlation_id=correlation_id,
        )


@lru_cache
def get_event_ingress() -> EventIngress:
    return EventIngress()
