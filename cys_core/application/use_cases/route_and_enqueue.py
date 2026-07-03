from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from cys_core.application.use_cases.dispatch_event import DispatchEvent, fallback_plan, use_async_investigation_planner
from cys_core.application.use_cases.plan_investigation import InvestigationPlan, PlanInvestigation
from cys_core.domain.events.models import RoutingDecision, SecurityEvent
from cys_core.application.routing.event_router import EventRouter
from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id


class RouteAndEnqueueEvent:
    """Route a security event and enqueue worker jobs for matched personas."""

    def __init__(
        self,
        *,
        router: EventRouter,
        enqueuer: Any,
        use_kafka: bool = False,
        publish_raw_event_sync: Callable[[SecurityEvent], bool] | None = None,
        publish_raw_event: Callable[[SecurityEvent], Awaitable[bool]] | None = None,
        record_event_ingested: Callable[[str], None] | None = None,
        plan_investigation: PlanInvestigation | None = None,
    ) -> None:
        self.router = router
        self.enqueuer = enqueuer
        self.use_kafka = use_kafka
        self.publish_raw_event_sync = publish_raw_event_sync
        self.publish_raw_event = publish_raw_event
        self.record_event_ingested = record_event_ingested or (lambda _event_type: None)
        self.plan_investigation = plan_investigation
        self._dispatcher = DispatchEvent(
            router=router,
            enqueuer=enqueuer,
            plan_investigation=plan_investigation,
            plan_executor=lambda event: fallback_plan(event),
        )

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
            type=event_type,  # type: ignore[arg-type]
            source=source,
            severity=severity,  # type: ignore[arg-type]
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
        cid_token = bind_correlation_id(event.correlation_id or event.id)
        try:
            self.record_event_ingested(event.type)
            sync_investigation = (
                event.type == "manual.investigation"
                and not use_async_investigation_planner(event, payload)
            )
            if self.use_kafka and self.publish_raw_event_sync and not sync_investigation:
                if self.publish_raw_event_sync(event):
                    decision = self.router.route(event)
                    return event, decision, []

            decision, job_ids = self._dispatcher.dispatch_sync(event, payload)
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
        cid_token = bind_correlation_id(event.correlation_id or event.id)
        try:
            self.record_event_ingested(event.type)
            sync_investigation = (
                event.type == "manual.investigation"
                and not use_async_investigation_planner(event, payload)
            )
            if self.use_kafka and self.publish_raw_event and not sync_investigation:
                if await self.publish_raw_event(event):
                    decision = self.router.route(event)
                    return event, decision, []

            decision, job_ids = await self._dispatcher.dispatch_async(event, payload)
            return event, decision, job_ids
        finally:
            reset_correlation_id(cid_token)

    def _fallback_plan(self, event: SecurityEvent) -> InvestigationPlan:
        return fallback_plan(event)
