from __future__ import annotations

from typing import Any

from cys_core.application.use_cases.start_engagement import StartEngagement
from cys_core.application.work_order.intake_normalizer import intake_memory_content, normalize_intake_to_event_payload
from cys_core.domain.catalog.models import ProfilePack
from cys_core.domain.engagement.models import Engagement, EngagementRequest, PlanStrategy
from cys_core.domain.events.models import RoutingDecision
from cys_core.domain.work_order.intake import WorkOrderIntake
from cys_core.domain.work_order.models import WorkOrderRequest
from cys_core.infrastructure.work_order.adapter import WorkOrderStore


class WorkOrderValidationError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class StartWorkOrder:
    def __init__(
        self,
        *,
        work_order_store: WorkOrderStore,
        start_engagement: StartEngagement,
        memory_writer=None,
        agent_catalog=None,
        metrics=None,
    ) -> None:
        self._work_order_store = work_order_store
        self._start_engagement = start_engagement
        self._memory_writer = memory_writer
        self._agent_catalog = agent_catalog
        self._metrics = metrics

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

    async def execute(self, request: WorkOrderRequest) -> tuple[Engagement, RoutingDecision, list[str]]:
        intake = self._validate_intake(request)
        goal = request.goal.strip() or intake.normalized_goal()
        engagement_request = EngagementRequest(
            profile_id=request.profile_id,
            domain_id=request.domain_id,
            goal=goal,
            mode=request.mode,
            plan_strategy=request.plan_strategy,
            input={**request.intake, "intake": dict(request.intake)},
            tenant_id=request.tenant_id,
            correlation_id=request.correlation_id,
        )
        engagement, decision, job_ids = await self._start_engagement.execute(engagement_request)
        self._work_order_store.sync_intake_to_engagement(request.tenant_id, engagement.id, dict(request.intake))
        if self._memory_writer is not None and request.intake:
            from cys_core.domain.memory.models import MemoryScope

            self._memory_writer.append(
                scope=MemoryScope(tenant_id=request.tenant_id, investigation_id=engagement.id),
                content=intake_memory_content(dict(request.intake)),
                memory_type="intake",
                source_agent="operator",
                source_job_id=f"work-order:{engagement.id}",
            )
        if self._metrics is not None:
            record = getattr(self._metrics, "record_work_order_created", None)
            if callable(record):
                record(request.profile_id)
        return engagement, decision, job_ids
