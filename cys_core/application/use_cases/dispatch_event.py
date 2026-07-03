from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from cys_core.application.advisory_goal import is_advisory_goal
from cys_core.application.runtime_config import (
    get_manual_investigation_async,
    get_use_conductor_for_events,
)
from cys_core.application.use_cases.plan_investigation import InvestigationPlan, PlanInvestigation
from cys_core.domain.events.models import RoutingDecision, SecurityEvent
from cys_core.application.routing.event_router import EventRouter
from cys_core.domain.runs.models import RunContext

ASYNC_PLANNER_PENDING = "async_planner_pending"


def _investigation_goal(payload: dict[str, Any]) -> str:
    return str(payload.get("goal", payload.get("message", "")))


def use_async_investigation_planner(event: SecurityEvent, payload: dict[str, Any]) -> bool:
    """Async 202 only for non-advisory investigations; advisory enqueues synchronously."""
    if event.type != "manual.investigation" or not get_manual_investigation_async():
        return False
    return not is_advisory_goal(_investigation_goal(payload))


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


class JobEnqueuer(Protocol):
    def enqueue_from_routing_sync(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
        sequential: bool = False,
    ) -> list[str]: ...

    async def enqueue_from_routing(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
        sequential: bool = False,
    ) -> list[str]: ...


def fallback_plan(event: SecurityEvent) -> InvestigationPlan:
    goal = str(event.payload.get("goal", event.payload.get("message", "Investigate security incident")))
    personas = PlanInvestigation.fallback_personas()
    return InvestigationPlan(
        personas=personas,
        sub_goals={persona: goal for persona in personas},
        rationale="sync_fallback_plan",
    )


class DispatchEvent:
    """Shared routing + enqueue logic for sync ingress and Kafka router consumer."""

    def __init__(
        self,
        *,
        router: EventRouter,
        enqueuer: JobEnqueuer,
        plan_investigation: PlanInvestigation | None = None,
        plan_executor: Callable[[SecurityEvent], InvestigationPlan] | None = None,
        async_plan_executor: Callable[[SecurityEvent], Awaitable[InvestigationPlan]] | None = None,
    ) -> None:
        self.router = router
        self.enqueuer = enqueuer
        self.plan_investigation = plan_investigation
        self._plan_executor = plan_executor
        self._async_plan_executor = async_plan_executor

    def dispatch_sync(self, event: SecurityEvent, payload: dict[str, Any]) -> tuple[RoutingDecision, list[str]]:
        if event.type == "manual.investigation" and self.plan_investigation is not None:
            plan = self._plan_executor(event) if self._plan_executor else fallback_plan(event)
            decision = RoutingDecision(
                event_id=event.id,
                personas=plan.personas,
                playbook_id="manual-investigation",
                notify_control=True,
                reason="llm_planner",
            )
            enriched = {**payload, **self.plan_investigation.to_worker_jobs_payload(plan)}
            job_ids = self.enqueuer.enqueue_from_routing_sync(
                event.id,
                plan.personas,
                playbook_id=decision.playbook_id,
                payload=enriched,
                correlation_id=event.correlation_id or event.id,
                tenant_id=event.tenant_id,
                sequential=True,
            )
            return decision, job_ids

        decision = self.router.route(event)
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
        if event.type == "manual.investigation" and self.plan_investigation is not None:
            if use_async_investigation_planner(event, payload):
                self.plan_investigation.begin_planning(event)
                decision = RoutingDecision(
                    event_id=event.id,
                    personas=[],
                    playbook_id="manual-investigation",
                    notify_control=True,
                    reason=ASYNC_PLANNER_PENDING,
                )
                return decision, []

            if self._async_plan_executor is not None:
                plan = await self._async_plan_executor(event)
            elif self.plan_investigation is not None:
                plan = await self.plan_investigation.execute(event)
            else:
                plan = fallback_plan(event)
            decision = RoutingDecision(
                event_id=event.id,
                personas=plan.personas,
                playbook_id="manual-investigation",
                notify_control=True,
                reason="llm_planner",
            )
            enriched = {**payload, **self.plan_investigation.to_worker_jobs_payload(plan)}
            job_ids = await self.enqueuer.enqueue_from_routing(
                event.id,
                plan.personas,
                playbook_id=decision.playbook_id,
                payload=enriched,
                correlation_id=event.correlation_id or event.id,
                tenant_id=event.tenant_id,
                sequential=bool(plan.depends_on),
            )
            return decision, job_ids

        decision = self.router.route(event)
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
