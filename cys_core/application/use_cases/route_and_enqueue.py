from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from cys_core.domain.events.models import RoutingDecision, SecurityEvent
from cys_core.domain.events.router import EventRouter
from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id


class JobEnqueuer(Protocol):
    def enqueue_from_routing_sync(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
    ) -> list[str]: ...

    async def enqueue_from_routing(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
    ) -> list[str]: ...


class RouteAndEnqueueEvent:
    """Route a security event and enqueue worker jobs for matched personas."""

    def __init__(
        self,
        *,
        router: EventRouter,
        enqueuer: JobEnqueuer,
        use_kafka: bool = False,
        publish_raw_event_sync: Callable[[SecurityEvent], bool] | None = None,
        publish_raw_event: Callable[[SecurityEvent], Awaitable[bool]] | None = None,
        record_event_ingested: Callable[[str], None] | None = None,
    ) -> None:
        self.router = router
        self.enqueuer = enqueuer
        self.use_kafka = use_kafka
        self.publish_raw_event_sync = publish_raw_event_sync
        self.publish_raw_event = publish_raw_event
        self.record_event_ingested = record_event_ingested or (lambda _event_type: None)

    def execute(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        severity: str = "medium",
        source: str = "",
        event_id: str | None = None,
        correlation_id: str = "",
    ) -> tuple[SecurityEvent, RoutingDecision, list[str]]:
        event = SecurityEvent(
            id=event_id or f"evt-{uuid.uuid4().hex[:12]}",
            type=event_type,  # type: ignore[arg-type]
            source=source,
            severity=severity,  # type: ignore[arg-type]
            payload=payload,
            correlation_id=correlation_id or "",
        )
        cid_token = bind_correlation_id(event.correlation_id or event.id)
        try:
            self.record_event_ingested(event.type)
            if self.use_kafka and self.publish_raw_event_sync and self.publish_raw_event_sync(event):
                decision = self.router.route(event)
                return event, decision, []

            decision = self.router.route(event)
            job_ids: list[str] = []
            if decision.personas:
                job_ids = self.enqueuer.enqueue_from_routing_sync(
                    event.id,
                    decision.personas,
                    playbook_id=decision.playbook_id,
                    payload=payload,
                    correlation_id=event.correlation_id or event.id,
                )
            return event, decision, job_ids
        finally:
            reset_correlation_id(cid_token)

    async def aexecute(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        severity: str = "medium",
        source: str = "",
        event_id: str | None = None,
        correlation_id: str = "",
    ) -> tuple[SecurityEvent, RoutingDecision, list[str]]:
        event = SecurityEvent(
            id=event_id or f"evt-{uuid.uuid4().hex[:12]}",
            type=event_type,  # type: ignore[arg-type]
            source=source,
            severity=severity,  # type: ignore[arg-type]
            payload=payload,
            correlation_id=correlation_id or "",
        )
        cid_token = bind_correlation_id(event.correlation_id or event.id)
        try:
            self.record_event_ingested(event.type)
            if self.use_kafka and self.publish_raw_event:
                if await self.publish_raw_event(event):
                    decision = self.router.route(event)
                    return event, decision, []

            decision = self.router.route(event)
            job_ids: list[str] = []
            if decision.personas:
                job_ids = await self.enqueuer.enqueue_from_routing(
                    event.id,
                    decision.personas,
                    playbook_id=decision.playbook_id,
                    payload=payload,
                    correlation_id=event.correlation_id or event.id,
                )
            return event, decision, job_ids
        finally:
            reset_correlation_id(cid_token)
