from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, cast

from cys_core.application.ports.tracing_ports import NOOP_APPLICATION_TRACING, ApplicationTracingPort, CorrelationIdPort
from cys_core.application.routing.event_router import EventRouter
from cys_core.application.use_cases.dispatch_event import DispatchEvent
from cys_core.application.use_cases.route_event import RouteEvent
from cys_core.domain.events.models import RoutingDecision, SecurityEvent, Severity


class RouteAndEnqueueEvent:
    """Route a security event and enqueue worker jobs for matched personas."""

    def __init__(
        self,
        *,
        route_event: RouteEvent | None = None,
        router: EventRouter | None = None,
        enqueuer: Any,
        correlation_id_port: CorrelationIdPort,
        use_kafka: bool = False,
        publish_raw_event_sync: Callable[[SecurityEvent], bool] | None = None,
        publish_raw_event: Callable[[SecurityEvent], Awaitable[bool]] | None = None,
        record_event_ingested: Callable[[str], None] | None = None,
        application_tracing: ApplicationTracingPort | None = None,
    ) -> None:
        if route_event is None:
            if router is None:
                raise TypeError("route_event or router is required")
            route_event = RouteEvent(router)
        self._route_event = route_event
        self.enqueuer = enqueuer
        self._correlation_id = correlation_id_port
        self.use_kafka = use_kafka
        self.publish_raw_event_sync = publish_raw_event_sync
        self.publish_raw_event = publish_raw_event
        self.record_event_ingested = record_event_ingested or (lambda _event_type: None)
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING
        self._dispatcher = DispatchEvent(
            route_event=route_event,
            enqueuer=enqueuer,
            application_tracing=self._tracing,
        )

    @property
    def router(self) -> EventRouter:
        return self._route_event._router

    def _build_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        severity: str,
        source: str,
        event_id: str | None,
        correlation_id: str,
        tenant_id: str = "default",
    ) -> SecurityEvent:
        return SecurityEvent(
            id=event_id or f"evt-{uuid.uuid4().hex[:12]}",
            type=event_type,
            source=source,
            severity=cast(Severity, severity),
            payload=payload,
            tenant_id=tenant_id,
            correlation_id=correlation_id or "",
        )

    def execute(
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
        event = self._build_event(
            event_type,
            payload,
            severity=severity,
            source=source,
            event_id=event_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
        )
        cid_token = self._correlation_id.bind(event.correlation_id or event.id)
        try:
            with self._tracing.span(
                "ingress.route_and_enqueue",
                event_type=event.type,
                engagement_id=event.correlation_id or event.id,
                tenant_id=event.tenant_id,
            ):
                self.record_event_ingested(event.type)
                if self.use_kafka and self.publish_raw_event_sync:
                    if self.publish_raw_event_sync(event):
                        decision = self._route_event.execute(event)
                        return event, decision, []

                decision, job_ids = self._dispatcher.dispatch_sync(event, payload)
                return event, decision, job_ids
        finally:
            self._correlation_id.reset(cid_token)

    async def aexecute(
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
        event = self._build_event(
            event_type,
            payload,
            severity=severity,
            source=source,
            event_id=event_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
        )
        cid_token = self._correlation_id.bind(event.correlation_id or event.id)
        try:
            with self._tracing.span(
                "ingress.route_and_enqueue",
                event_type=event.type,
                engagement_id=event.correlation_id or event.id,
                tenant_id=event.tenant_id,
            ):
                self.record_event_ingested(event.type)
                if self.use_kafka and self.publish_raw_event:
                    if await self.publish_raw_event(event):
                        decision = self._route_event.execute(event)
                        return event, decision, []

                decision, job_ids = await self._dispatcher.dispatch_async(event, payload)
                return event, decision, job_ids
        finally:
            self._correlation_id.reset(cid_token)
