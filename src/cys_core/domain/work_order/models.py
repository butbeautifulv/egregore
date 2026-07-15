from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.engagement.models import EngagementMode, PlanStrategy
from cys_core.domain.follow_up.models import FollowUpMode


class WorkOrderStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    ENQUEUED = "enqueued"
    RUNNING = "running"
    CLOSED = "closed"
    FAILED = "failed"


class WorkOrderRequest(BaseModel):
    profile_id: str = "cybersec-soc"
    domain_id: str = ""
    workspace_id: str = ""
    goal: str = ""
    intake: dict[str, Any] = Field(default_factory=dict)
    mode: EngagementMode = EngagementMode.ASYNC
    plan_strategy: PlanStrategy = PlanStrategy.META_LLM
    intent_mode: FollowUpMode = "auto"
    tenant_id: str = "default"
    correlation_id: str = ""

    def effective_goal(self) -> str:
        if self.goal.strip():
            return self.goal.strip()
        return str(self.intake.get("goal", "")).strip()

    def to_engagement_request(self, work_order_id: str):
        from cys_core.domain.engagement.models import EngagementRequest

        goal = self.effective_goal()
        return EngagementRequest(
            profile_id=self.profile_id,
            domain_id=self.domain_id,
            workspace_id=self.workspace_id,
            goal=goal,
            mode=self.mode,
            plan_strategy=self.plan_strategy,
            input={**self.intake, "intake": dict(self.intake)},
            tenant_id=self.tenant_id,
            correlation_id=self.correlation_id or work_order_id,
            intent_mode=self.intent_mode,
        )


class WorkOrder(BaseModel):
    id: str
    tenant_id: str = "default"
    profile_id: str = "cybersec-soc"
    domain_id: str = ""
    workspace_id: str = ""
    goal: str = ""
    status: WorkOrderStatus = WorkOrderStatus.CREATED
    intake: dict[str, Any] = Field(default_factory=dict)
    job_ids: list[str] = Field(default_factory=list)
    correlation_id: str = ""
