from __future__ import annotations

import uuid

from cys_core.application.follow_up.intent import classify_operator_intent, orchestrator_persona_for
from cys_core.application.operator_messages.service import (
    initial_follow_up_id,
    persist_operator_turn_to_memory,
)
from cys_core.application.ports.authz import AuthzTuple
from cys_core.application.ports.work_order import WorkOrderStorePort
from cys_core.application.use_cases.ensure_default_workspace import ensure_default_workspace
from cys_core.application.use_cases.start_engagement import StartEngagement
from cys_core.application.work_order.intake_normalizer import intake_memory_content
from cys_core.domain.catalog.models import ProfilePack
from cys_core.domain.engagement.models import Engagement, EngagementRequest
from cys_core.domain.events.models import RoutingDecision
from cys_core.domain.follow_up.models import FOLLOW_UP_PHASE
from cys_core.domain.work_order.intake import WorkOrderIntake
from cys_core.domain.work_order.models import WorkOrderRequest
from cys_core.domain.workers.models import WorkerJob

INITIAL_QA_PENDING = "initial_qa_pending"


def engagement_authz_tuples(engagement_id: str, workspace_id: str) -> list[AuthzTuple]:
    ws_id = (workspace_id or "").strip()
    if not ws_id:
        return []
    return [
        AuthzTuple(
            user=f"workspace:{ws_id}",
            relation="workspace",
            object=f"engagement:{engagement_id}",
        )
    ]


class WorkOrderValidationError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class StartWorkOrder:
    def __init__(
        self,
        *,
        work_order_store: WorkOrderStorePort,
        start_engagement: StartEngagement,
        memory_writer=None,
        memory_reader=None,
        agent_catalog=None,
        metrics=None,
        job_store=None,
        queue=None,
        engagement_egress=None,
        engagement_store=None,
        workspace_store=None,
        authz_tuple_writer=None,
    ) -> None:
        self._work_order_store = work_order_store
        self._start_engagement = start_engagement
        self._memory_writer = memory_writer
        self._memory_reader = memory_reader
        self._agent_catalog = agent_catalog
        self._metrics = metrics
        self._job_store = job_store
        self._queue = queue
        self._engagement_egress = engagement_egress
        self._engagement_store = engagement_store
        self._workspace_store = workspace_store
        self._authz_tuple_writer = authz_tuple_writer

    def _profile_pack(self, profile_id: str) -> ProfilePack | None:
        if self._agent_catalog is None:
            return None
        for profile in self._agent_catalog.list_profiles():
            if profile.id == profile_id:
                return profile
        return None

    def _validate_intake(self, request: WorkOrderRequest) -> WorkOrderIntake:
        intake = WorkOrderIntake.model_validate(request.intake)
        if not intake.normalized_goal() and not request.goal.strip():
            raise WorkOrderValidationError("goal_required", status_code=400)
        profile = self._profile_pack(request.profile_id)
        schema = profile.intake_schema if profile is not None else {}
        if schema:
            try:
                import jsonschema
            except ImportError:
                pass
            else:
                try:
                    jsonschema.validate(instance=request.intake, schema=schema)
                except jsonschema.ValidationError as exc:
                    raise WorkOrderValidationError(str(exc.message), status_code=400) from exc
        return intake

    def _engagement_request(
        self,
        request: WorkOrderRequest,
        goal: str,
        *,
        skip_dispatch: bool = False,
    ) -> EngagementRequest:
        engagement_id = request.correlation_id or f"eng-{uuid.uuid4().hex[:12]}"
        return EngagementRequest(
            profile_id=request.profile_id,
            domain_id=request.domain_id,
            workspace_id=request.workspace_id,
            goal=goal,
            mode=request.mode,
            plan_strategy=request.plan_strategy,
            input={**request.intake, "intake": dict(request.intake)},
            tenant_id=request.tenant_id,
            correlation_id=engagement_id,
            intent_mode=request.intent_mode,
            skip_dispatch=skip_dispatch,
        )

    def _with_workspace(self, request: WorkOrderRequest) -> WorkOrderRequest:
        if request.workspace_id.strip() or self._workspace_store is None:
            return request
        workspace = ensure_default_workspace(
            self._workspace_store,
            request.tenant_id,
            write_tuples=self._authz_tuple_writer,
        )
        return request.model_copy(update={"workspace_id": workspace.id})

    def _persist_intake_memory(self, request: WorkOrderRequest, engagement_id: str) -> None:
        if self._memory_writer is None or not request.intake:
            return
        from cys_core.domain.memory.models import MemoryScope

        self._memory_writer.append(
            scope=MemoryScope(
                tenant_id=request.tenant_id,
                investigation_id=engagement_id,
                workspace_id=request.workspace_id,
            ),
            content=intake_memory_content(dict(request.intake)),
            memory_type="intake",
            source_agent="operator",
            source_job_id=f"work-order:{engagement_id}",
        )

    def _persist_initial_turn(
        self,
        request: WorkOrderRequest,
        engagement_id: str,
        goal: str,
        *,
        work_kind: str = "",
    ) -> str:
        if self._memory_writer is None:
            return initial_follow_up_id(engagement_id)
        fu_id = initial_follow_up_id(engagement_id)
        persist_operator_turn_to_memory(
            self._memory_writer,
            tenant_id=request.tenant_id,
            engagement_id=engagement_id,
            message=goal,
            follow_up_id=fu_id,
            work_kind=work_kind,
            mode=request.intent_mode,
            metrics=self._metrics,
            memory_reader=self._memory_reader,
            engagement_store=self._engagement_store,
        )
        return fu_id

    def _enqueue_initial_qa_job(
        self,
        *,
        tenant_id: str,
        engagement_id: str,
        follow_up_id: str,
        goal: str,
        workspace_id: str = "",
    ) -> str:
        if self._job_store is None or self._queue is None:
            raise WorkOrderValidationError("initial_qa_unavailable", status_code=503)
        persona = orchestrator_persona_for("initial_qa")
        job_id = f"{persona}-fu-{uuid.uuid4().hex[:8]}"
        job = WorkerJob(
            job_id=job_id,
            event_id=engagement_id,
            persona=persona,
            correlation_id=engagement_id,
            tenant_id=tenant_id,
            payload={
                "phase": FOLLOW_UP_PHASE,
                "work_kind": "initial_qa",
                "operator_message": goal.strip(),
                "follow_up_id": follow_up_id,
                "goal": goal,
                "context_id": engagement_id,
                "workspace_id": workspace_id,
            },
        )
        self._job_store.upsert_pending(
            job.job_id,
            job.persona,
            correlation_id=job.correlation_id,
            tenant_id=job.tenant_id,
            event_id=job.event_id,
        )
        self._queue.enqueue(job)
        if self._metrics is not None:
            record = getattr(self._metrics, "record_follow_up_queued", None)
            if callable(record):
                record("initial_qa")
            record_intent = getattr(self._metrics, "record_work_order_intent", None)
            if callable(record_intent):
                record_intent("qa")
        if self._engagement_egress is not None:
            self._engagement_egress.publish_event(
                engagement_id,
                "follow_up_queued",
                {
                    "tenant_id": tenant_id,
                    "follow_up_id": follow_up_id,
                    "work_kind": "initial_qa",
                    "job_id": job_id,
                },
            )
        engagement = self._engagement_store.get(tenant_id, engagement_id) if self._engagement_store else None
        store = self._engagement_store
        if engagement is not None and store is not None:
            engagement.mark_enqueued([job_id])
            store.upsert(engagement)
        return job_id

    async def _execute_initial_qa(
        self,
        request: WorkOrderRequest,
        goal: str,
    ) -> tuple[Engagement, RoutingDecision, list[str]]:
        engagement_request = self._engagement_request(request, goal, skip_dispatch=True)
        engagement, _decision, _job_ids = await self._start_engagement.execute(engagement_request)
        self._work_order_store.sync_intake_to_engagement(request.tenant_id, engagement.id, dict(request.intake))
        self._persist_intake_memory(request, engagement.id)
        follow_up_id = self._persist_initial_turn(
            request,
            engagement.id,
            goal,
            work_kind="initial_qa",
        )
        job_id = self._enqueue_initial_qa_job(
            tenant_id=request.tenant_id,
            engagement_id=engagement.id,
            follow_up_id=follow_up_id,
            goal=goal,
            workspace_id=request.workspace_id,
        )
        decision = RoutingDecision(
            event_id=engagement.id,
            personas=[],
            playbook_id="",
            notify_control=False,
            reason=INITIAL_QA_PENDING,
        )
        if self._metrics is not None:
            record = getattr(self._metrics, "record_work_order_created", None)
            if callable(record):
                record(request.profile_id)
        return engagement, decision, [job_id]

    async def execute(self, request: WorkOrderRequest) -> tuple[Engagement, RoutingDecision, list[str]]:
        request = self._with_workspace(request)
        intake = self._validate_intake(request)
        goal = request.goal.strip() or intake.normalized_goal()
        work_kind = classify_operator_intent(
            goal,
            mode=request.intent_mode,  # type: ignore[arg-type]
            context="initial",
            prior_operator_turns=0,
        )
        if work_kind == "initial_qa":
            return await self._execute_initial_qa(request, goal)

        engagement_request = self._engagement_request(request, goal)
        engagement, decision, job_ids = await self._start_engagement.execute(engagement_request)
        if self._authz_tuple_writer is not None and request.workspace_id.strip():
            self._authz_tuple_writer(engagement_authz_tuples(engagement.id, request.workspace_id))
        self._work_order_store.sync_intake_to_engagement(request.tenant_id, engagement.id, dict(request.intake))
        self._persist_intake_memory(request, engagement.id)
        planner_work_kind = "follow_up_plan" if work_kind == "follow_up_plan" else ""
        self._persist_initial_turn(
            request,
            engagement.id,
            goal,
            work_kind=planner_work_kind,
        )
        if self._metrics is not None:
            record = getattr(self._metrics, "record_work_order_created", None)
            if callable(record):
                record(request.profile_id)
            record_intent = getattr(self._metrics, "record_work_order_intent", None)
            if callable(record_intent):
                record_intent(request.intent_mode)
        return engagement, decision, job_ids
