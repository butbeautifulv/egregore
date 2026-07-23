from __future__ import annotations

import uuid
from typing import Any

from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.tracing_ports import (
    NOOP_APPLICATION_TRACING,
    ApplicationTracingPort,
    CorrelationIdPort,
    TraceFlushPort,
)

# re-export for callers
from cys_core.application.use_cases.engagement_planner import ASYNC_PLANNER_PENDING
from cys_core.domain.engagement.models import (
    Engagement,
    EngagementRequest,
    EngagementStatus,
    PlanStrategy,
)
from cys_core.domain.engagement.planner_job import (
    ENGAGEMENT_PLAN_WORK_KIND,
    ENGAGEMENT_PLANNER_PERSONA,
)
from cys_core.domain.events.models import RoutingDecision, SecurityEvent
from cys_core.domain.security.factory import get_input_sanitizer


def engagement_request_to_security_event(request: EngagementRequest, engagement_id: str) -> SecurityEvent:
    payload: dict[str, Any] = {
        "goal": request.goal,
        "message": request.goal,
        **request.input,
        "profile_id": request.profile_id,
        "domain_id": request.domain_id,
        "workspace_id": request.workspace_id,
        "plan_strategy": request.plan_strategy.value,
        "engagement_mode": request.mode.value,
        "intent_mode": request.intent_mode,
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


class StartEngagement:
    """Create engagement record and dispatch through orchestration."""

    def __init__(
        self,
        *,
        engagement_store: EngagementStateStore,
        dispatch,
        egress=None,
        correlation_id_port: CorrelationIdPort | None = None,
        trace_flush_port: TraceFlushPort | None = None,
        application_tracing: ApplicationTracingPort | None = None,
    ) -> None:
        self.engagement_store = engagement_store
        self.dispatch = dispatch
        self.egress = egress
        self._correlation_id = correlation_id_port
        self._trace_flush = trace_flush_port
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING

    def _new_id(self) -> str:
        return f"eng-{uuid.uuid4().hex[:12]}"

    async def execute(self, request: EngagementRequest) -> tuple[Engagement, RoutingDecision, list[str]]:
        # 5-whys root cause fix (docs/MSP_BACKLOG.md §11.7/§13 Phase 12):
        # this is the one place every ingress path (POST /v1/engagements,
        # engagement_ingress.py's event-driven path, and any future one) converges
        # before `goal` is persisted/published — sanitizing here means no ingress
        # route can forget to, and every downstream consumer of the queue/job_store
        # (not just the worker, which already sanitizes on its own before an LLM
        # call) sees filtered content, not a raw injection payload.
        request = request.model_copy(
            update={"goal": get_input_sanitizer().filter_patterns(request.goal)}
        )
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
            workspace_id=request.workspace_id,
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

        if request.skip_dispatch:
            decision = RoutingDecision(
                event_id=event.id,
                personas=[],
                playbook_id="",
                notify_control=False,
                reason="record_only",
            )
            return engagement, decision, []

        if request.plan_strategy == PlanStrategy.META_LLM:
            # Meta-LLM planning calls the real agent runtime
            # (catalog_planner_strategy.py's self.runtime.arun(...)), which api
            # must never construct (docs/MSP_BACKLOG.md §0/§1.2).
            # Enqueue a WorkerJob(persona="planner", work_kind="engagement_plan")
            # instead of running a planner in-process — worker's RunWorkerJob
            # recognizes it (is_engagement_plan_job) and hands it to
            # EngagementPlannerRunner, the real planner with the real runtime,
            # which enqueues the resulting persona jobs itself once the plan is
            # ready. This is always async now; there is no in-process fallback.
            engagement.begin_planning(goal=request.goal)
            self.engagement_store.upsert(engagement)
            if self.egress is not None:
                self.egress.publish_status(engagement_id, "planning", {"tenant_id": request.tenant_id})
            await self.dispatch.enqueuer.enqueue_from_routing(
                event.id,
                [ENGAGEMENT_PLANNER_PERSONA],
                playbook_id="engagement-meta-llm",
                payload={**payload, "work_kind": ENGAGEMENT_PLAN_WORK_KIND},
                correlation_id=engagement.correlation_id,
                tenant_id=request.tenant_id,
                profile_id=engagement.profile_id,
                sequential=False,
            )
            engagement = self.engagement_store.get(request.tenant_id, engagement_id) or engagement
            decision = RoutingDecision(
                event_id=event.id,
                personas=[],
                playbook_id="engagement-meta-llm",
                notify_control=True,
                reason=ASYNC_PLANNER_PENDING,
            )
            return engagement, decision, []

        decision, job_ids = await self.dispatch.dispatch_async(event, payload)

        engagement = self.engagement_store.get(request.tenant_id, engagement_id) or engagement
        engagement.mark_enqueued(job_ids)
        self.engagement_store.upsert(engagement)
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
