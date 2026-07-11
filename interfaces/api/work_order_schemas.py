from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.engagement.models import EngagementMode, PlanStrategy
from cys_core.domain.work_order.models import WorkOrder, WorkOrderRequest, WorkOrderStatus


class WorkOrderCreateIn(BaseModel):
    profile_id: str = "cybersec-soc"
    domain_id: str = ""
    goal: str = ""
    intake: dict[str, Any] = Field(default_factory=dict)
    mode: EngagementMode = EngagementMode.ASYNC
    plan_strategy: PlanStrategy = PlanStrategy.META_LLM
    tenant_id: str = "default"
    correlation_id: str = ""

    def to_domain_request(self) -> WorkOrderRequest:
        return WorkOrderRequest(**self.model_dump())


class WorkOrderOut(BaseModel):
    work_order_id: str
    status: str
    profile_id: str
    domain_id: str = ""
    goal: str = ""
    intake: dict[str, Any] = Field(default_factory=dict)
    job_ids: list[str] = Field(default_factory=list)
    playbook_id: str = ""
    reason: str = ""
    completed_personas: list[str] = Field(default_factory=list)
    failed_personas: list[str] = Field(default_factory=list)
    planner_plan: list[str] | None = None
    planner_status: str | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_domain(cls, work_order: WorkOrder, *, decision=None, job_ids=None) -> WorkOrderOut:
        return cls(
            work_order_id=work_order.id,
            status=work_order.status.value,
            profile_id=work_order.profile_id,
            domain_id=work_order.domain_id,
            goal=work_order.goal,
            intake=dict(work_order.intake),
            job_ids=job_ids if job_ids is not None else list(work_order.job_ids),
            playbook_id=decision.playbook_id if decision is not None else "",
            reason=decision.reason if decision is not None else "",
        )

    @classmethod
    def from_engagement(
        cls,
        engagement,
        *,
        decision=None,
        job_ids=None,
        updated_at: datetime | None = None,
    ) -> WorkOrderOut:
        return cls(
            work_order_id=engagement.id,
            status=engagement.status.value,
            profile_id=engagement.profile_id,
            domain_id=engagement.domain_id,
            goal=engagement.goal,
            intake=dict(getattr(engagement, "intake", None) or {}),
            job_ids=job_ids if job_ids is not None else list(engagement.job_ids),
            playbook_id=decision.playbook_id if decision is not None else "",
            reason=decision.reason if decision is not None else "",
            completed_personas=list(engagement.completed_personas),
            failed_personas=list(engagement.failed_personas),
            planner_plan=engagement.planner_plan,
            planner_status=engagement.planner_status,
            updated_at=updated_at,
        )


class WorkOrderListOut(BaseModel):
    work_orders: list[WorkOrderOut] = Field(default_factory=list)
