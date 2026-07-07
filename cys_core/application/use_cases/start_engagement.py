from __future__ import annotations

import uuid
from typing import Any

from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.tracing_ports import ApplicationTracingPort, CorrelationIdPort, NOOP_APPLICATION_TRACING, TraceFlushPort
from cys_core.domain.engagement.models import (
    Engagement,
    EngagementMode,
    EngagementPlan,
    EngagementRequest,
    EngagementStatus,
    ExecutionMode,
    PlanStrategy,
)

# re-export for callers
from cys_core.application.use_cases.engagement_planner import (
    ASYNC_PLANNER_PENDING,
    use_async_engagement_planner,
)
from cys_core.domain.events.models import RoutingDecision, SecurityEvent


def engagement_request_to_security_event(request: EngagementRequest, engagement_id: str) -> SecurityEvent:
    payload: dict[str, Any] = {
        "goal": request.goal,
        "message": request.goal,
        **request.input,
        "profile_id": request.profile_id,
        "domain_id": request.domain_id,
        "plan_strategy": request.plan_strategy.value,
        "engagement_mode": request.mode.value,
    }
    return SecurityEvent(
        id=engagement_id,
        type="engagement.start",
        payload=payload,
        severity="medium",
        source="engagement-api",
        correlation_id=request.correlation_id or engagement_id,
        tenant_id=request.tenant_id,
    )


def _pipeline_staged(plan: EngagementPlan) -> bool:
    return plan.effective_execution_mode() == ExecutionMode.STAGED and len(plan.personas) > 1


class StartEngagement:
    """Create engagement record and dispatch through orchestration."""

    def __init__(
        self,
        *,
        engagement_store: EngagementStateStore,
        dispatch,
        egress=None,
        meta_planner=None,
        correlation_id_port: CorrelationIdPort | None = None,
        trace_flush_port: TraceFlushPort | None = None,
        application_tracing: ApplicationTracingPort | None = None,
    ) -> None:
        self.engagement_store = engagement_store
        self.dispatch = dispatch
        self.egress = egress
        self.meta_planner = meta_planner
        self._correlation_id = correlation_id_port
        self._trace_flush = trace_flush_port
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING

    def _new_id(self) -> str:
        return f"eng-{uuid.uuid4().hex[:12]}"

    async def execute(self, request: EngagementRequest) -> tuple[Engagement, RoutingDecision, list[str]]:
        engagement_id = request.correlation_id or self._new_id()
        with self._tracing.span(
            "engagement.start",
            engagement_id=engagement_id,
            tenant_id=request.tenant_id,
        ):
            return await self._execute_start(request, engagement_id)

    async def _execute_start(
        self, request: EngagementRequest, engagement_id: str
    ) -> tuple[Engagement, RoutingDecision, list[str]]:
        engagement = Engagement(
            id=engagement_id,
            tenant_id=request.tenant_id,
            profile_id=request.profile_id,
            domain_id=request.domain_id,
            goal=request.goal,
            mode=request.mode,
            status=EngagementStatus.CREATED,
            correlation_id=request.correlation_id or engagement_id,
            plan_strategy=request.plan_strategy,
        )
        self.engagement_store.upsert(engagement)
        if self.egress is not None:
            self.egress.publish_status(
                engagement_id,
                "created",
                {"tenant_id": request.tenant_id, "goal": request.goal},
            )

        event = engagement_request_to_security_event(request, engagement_id)
        payload = dict(event.payload)

        meta_planner_sync = False
        if request.plan_strategy == PlanStrategy.META_LLM and self.meta_planner is not None:
            if use_async_engagement_planner(event, payload):
                self.meta_planner.begin_planning(event)
                if self.egress is not None:
                    self.egress.publish_status(engagement_id, "planning", {"tenant_id": request.tenant_id})
                engagement = self.engagement_store.get(request.tenant_id, engagement_id) or engagement
                decision = RoutingDecision(
                    event_id=event.id,
                    personas=[],
                    playbook_id="engagement-meta-llm",
                    notify_control=True,
                    reason=ASYNC_PLANNER_PENDING,
                )
                return engagement, decision, []

            if self.egress is not None:
                self.egress.publish_status(engagement_id, "planning", {"tenant_id": request.tenant_id})
            plan = await self.meta_planner.execute(event, profile_id=request.profile_id)
            decision = RoutingDecision(
                event_id=event.id,
                personas=plan.personas,
                playbook_id="engagement-meta-llm",
                notify_control=True,
                reason="meta_planner",
            )
            enriched = {**payload, **self.meta_planner.to_worker_jobs_payload(plan)}
            job_ids = await self.dispatch.enqueuer.enqueue_from_routing(
                event.id,
                plan.personas,
                playbook_id=decision.playbook_id,
                payload=enriched,
                correlation_id=engagement.correlation_id,
                tenant_id=request.tenant_id,
                sequential=False,
                pipeline_staged=_pipeline_staged(plan),
            )
            meta_planner_sync = True
        else:
            decision, job_ids = await self.dispatch.dispatch_async(event, payload)

        engagement = self.engagement_store.get(request.tenant_id, engagement_id) or engagement
        engagement.mark_enqueued(job_ids)
        self.engagement_store.upsert(engagement)
        if meta_planner_sync and self._trace_flush is not None:
            self._trace_flush.flush_traces()
        if self.egress is not None:
            self.egress.publish_status(
                engagement_id,
                engagement.status.value,
                {"tenant_id": request.tenant_id, "job_ids": job_ids},
            )
        return engagement, decision, job_ids

    def get(self, engagement_id: str, *, tenant_id: str = "default") -> Engagement | None:
        state = self.engagement_store.get(tenant_id, engagement_id)
        if state is None:
            return None
        return state

    async def plan_async_background(self, event: SecurityEvent, payload: dict[str, Any]) -> list[str]:
        """Run meta-LLM planner in background after HTTP 202."""
        from cys_core.application.errors import PlanningFailedError

        engagement_id = event.correlation_id or event.id
        token = self._correlation_id.bind(engagement_id) if self._correlation_id is not None else None
        try:
            if self.meta_planner is None:
                return []
            self.meta_planner.begin_planning(event)
            if self.egress is not None:
                self.egress.publish_status(engagement_id, "planning", {"tenant_id": event.tenant_id})
            try:
                plan = await self.meta_planner.execute(event)
                enriched = {**payload, **self.meta_planner.to_worker_jobs_payload(plan)}
                job_ids = await self.dispatch.enqueuer.enqueue_from_routing(
                    event.id,
                    plan.personas,
                    playbook_id="engagement-meta-llm",
                    payload=enriched,
                    correlation_id=engagement_id,
                    tenant_id=event.tenant_id,
                    sequential=False,
                    pipeline_staged=_pipeline_staged(plan),
                )
                engagement = self.engagement_store.get(event.tenant_id, engagement_id)
                if engagement is not None:
                    engagement.mark_enqueued(job_ids)
                    self.engagement_store.upsert(engagement)
                if self.egress is not None:
                    self.egress.publish_status(
                        engagement_id,
                        "enqueued",
                        {
                            "tenant_id": event.tenant_id,
                            "job_ids": job_ids,
                            "personas": plan.personas,
                        },
                    )
                return job_ids
            except Exception as exc:
                if self.egress is not None:
                    self.egress.publish_status(
                        engagement_id,
                        "error",
                        {"tenant_id": event.tenant_id, "planner_error": str(exc)},
                    )
                raise PlanningFailedError(event.id, str(exc)) from exc
            finally:
                if self._trace_flush is not None:
                    self._trace_flush.flush_traces()
        finally:
            if self._correlation_id is not None and token is not None:
                self._correlation_id.reset(token)
