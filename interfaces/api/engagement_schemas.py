from __future__ import annotations

from datetime import datetime
from typing import Any

from cys_core.domain.engagement.models import EngagementMode, EngagementRequest, PlanStrategy
from pydantic import BaseModel, Field


class EngagementCreateIn(BaseModel):
    profile_id: str = "cybersec-soc"
    domain_id: str = ""
    goal: str
    mode: EngagementMode = EngagementMode.ASYNC
    plan_strategy: PlanStrategy = PlanStrategy.DECLARATIVE
    input: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = "default"
    correlation_id: str = ""

    model_config = {"from_attributes": True}

    def to_domain_request(self) -> EngagementRequest:
        return EngagementRequest(**self.model_dump())


class EngagementOut(BaseModel):
    engagement_id: str
    status: str
    latest_phase: str | None = None
    job_ids: list[str] = Field(default_factory=list)
    playbook_id: str = ""
    reason: str = ""
    goal: str = ""
    completed_personas: list[str] = Field(default_factory=list)
    failed_personas: list[str] = Field(default_factory=list)
    planner_plan: list[str] | None = None
    planner_status: str | None = None
    planner_rationale: str = ""
    planner_error: str = ""
    findings_summary: list[dict[str, Any]] = Field(default_factory=list)


class EngagementListOut(BaseModel):
    engagements: list[EngagementOut] = Field(default_factory=list)


class MemoryEntryOut(BaseModel):
    id: str
    investigation_id: str = ""
    source_agent: str
    source_job_id: str
    memory_type: str
    trust_score: float
    content: str
    content_parsed: dict[str, Any] | None = None
    created_at: datetime


class EngagementMemoryOut(BaseModel):
    entries: list[MemoryEntryOut] = Field(default_factory=list)


class TenantMemoryOut(BaseModel):
    entries: list[MemoryEntryOut] = Field(default_factory=list)


class PromotePlanIn(BaseModel):
    plan_id: str
    activate: bool = False
