from __future__ import annotations

from typing import Any

from cys_core.application.ports.orchestration import OrchestrationPort
from cys_core.application.ports.tracing_ports import ApplicationTracingPort, NOOP_APPLICATION_TRACING
from cys_core.application.use_cases.route_event import RouteEvent
from cys_core.application.routing.event_router import EventRouter
from cys_core.application.runtime_config import get_use_conductor_for_events
from cys_core.domain.catalog.profile_id import resolve_profile_id
from cys_core.domain.events.models import RoutingDecision, SecurityEvent
from cys_core.domain.runs.models import RunContext

def enrich_payload_with_run_context(event: SecurityEvent, payload: dict[str, Any]) -> dict[str, Any]:
    """Attach RunContext(kind=event) — no session required."""
    ctx = RunContext.from_event(event)
    return {**payload, "run_context": ctx.model_dump()}


def apply_conductor_routing(
    event: SecurityEvent,
    decision: RoutingDecision,
    payload: dict[str, Any],
) -> tuple[RoutingDecision, dict[str, Any]]:
    """Optional meta-worker routing: conductor orchestrates suggested personas."""
    if not get_use_conductor_for_events() or not decision.personas:
        return decision, enrich_payload_with_run_context(event, payload)
    from cys_core.application.plans_as_hints import load_plan_hints

    enriched = enrich_payload_with_run_context(event, payload)
    enriched["routing_hints"] = load_plan_hints()
    enriched["suggested_personas"] = list(decision.personas)
    conductor_decision = RoutingDecision(
        event_id=decision.event_id,
        personas=["conductor"],
        playbook_id=decision.playbook_id,
        notify_control=decision.notify_control,
        reason="conductor_meta_worker",
    )
    return conductor_decision, enriched


class DispatchEvent:
    """Declarative routing + enqueue for SIEM and non-meta-LLM events."""

    def __init__(
        self,
        *,
        route_event: RouteEvent | None = None,
        router: EventRouter | None = None,
        enqueuer: OrchestrationPort,
        application_tracing: ApplicationTracingPort | None = None,
    ) -> None:
        if route_event is None:
            if router is None:
                raise TypeError("route_event or router is required")
            route_event = RouteEvent(router)
        self._route_event = route_event
        self.enqueuer = enqueuer
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING

    def dispatch_sync(self, event: SecurityEvent, payload: dict[str, Any]) -> tuple[RoutingDecision, list[str]]:
        with self._tracing.span(
            "ingress.dispatch",
            event_type=event.type,
            engagement_id=event.correlation_id or event.id,
            tenant_id=event.tenant_id,
        ):
            profile_id = resolve_profile_id(payload=payload)
            decision = self._route_event.execute(event, profile_id=profile_id)
            job_ids: list[str] = []
            if decision.personas:
                decision, enriched_payload = apply_conductor_routing(event, decision, payload)
                job_ids = self.enqueuer.enqueue_from_routing_sync(
                    event.id,
                    decision.personas,
                    playbook_id=decision.playbook_id,
                    payload=enriched_payload,
                    correlation_id=event.correlation_id or event.id,
                    tenant_id=event.tenant_id,
                    sequential=False,
                )
            return decision, job_ids

    async def dispatch_async(self, event: SecurityEvent, payload: dict[str, Any]) -> tuple[RoutingDecision, list[str]]:
        with self._tracing.span(
            "ingress.dispatch",
            event_type=event.type,
            engagement_id=event.correlation_id or event.id,
            tenant_id=event.tenant_id,
        ):
            profile_id = resolve_profile_id(payload=payload)
            decision = self._route_event.execute(event, profile_id=profile_id)
            job_ids: list[str] = []
            if decision.personas:
                decision, enriched_payload = apply_conductor_routing(event, decision, payload)
                job_ids = await self.enqueuer.enqueue_from_routing(
                    event.id,
                    decision.personas,
                    playbook_id=decision.playbook_id,
                    payload=enriched_payload,
                    correlation_id=event.correlation_id or event.id,
                    tenant_id=event.tenant_id,
                    sequential=False,
                )
            return decision, job_ids
