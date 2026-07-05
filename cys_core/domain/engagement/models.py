from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class EngagementStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    ENQUEUED = "enqueued"
    RUNNING = "running"
    CLOSED = "closed"
    FAILED = "failed"


class EngagementMode(StrEnum):
    ASYNC = "async"
    INTERACTIVE = "interactive"


class PlanStrategy(StrEnum):
    DECLARATIVE = "declarative"
    META_LLM = "meta_llm"


class EngagementPlan(BaseModel):
    personas: list[str] = Field(default_factory=list)
    sub_goals: dict[str, str] = Field(default_factory=dict)
    depends_on: dict[str, list[str]] = Field(default_factory=dict)
    plan_id: str = ""
    strategy: PlanStrategy = PlanStrategy.DECLARATIVE
    rationale: str = ""
    reasoning_steps: list[str] = Field(default_factory=list)
    plan_status: str = ""


class EngagementRequest(BaseModel):
    profile_id: str = "cybersec-soc"
    domain_id: str = ""
    goal: str
    mode: EngagementMode = EngagementMode.ASYNC
    plan_strategy: PlanStrategy = PlanStrategy.DECLARATIVE
    input: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = "default"
    correlation_id: str = ""


class Engagement(BaseModel):
    id: str
    tenant_id: str = "default"
    profile_id: str = "cybersec-soc"
    domain_id: str = ""
    goal: str
    mode: EngagementMode = EngagementMode.ASYNC
    status: EngagementStatus = EngagementStatus.CREATED
    correlation_id: str = ""
    plan_strategy: PlanStrategy = PlanStrategy.DECLARATIVE
    job_ids: list[str] = Field(default_factory=list)
    completed_personas: list[str] = Field(default_factory=list)
    failed_personas: list[str] = Field(default_factory=list)
    findings_summary: list[dict[str, Any]] = Field(default_factory=list)
    planner_plan: list[str] | None = None
    planner_status: str | None = None
    planner_rationale: str = ""
    planner_error: str = ""

    def begin_planning(self, *, goal: str | None = None) -> None:
        if goal is not None:
            self.goal = goal
        if self.status == EngagementStatus.CREATED:
            self.status = EngagementStatus.PLANNING
        self.planner_status = "planning"
        self.planner_plan = None
        self.planner_rationale = ""
        self.planner_error = ""

    def mark_enqueued(self, job_ids: list[str]) -> None:
        self.status = EngagementStatus.ENQUEUED if job_ids else EngagementStatus.PLANNING
        self.job_ids = list(job_ids)

    def _terminal_personas(self) -> set[str]:
        return set(self.completed_personas) | set(self.failed_personas)

    def record_persona_completed(self, persona: str, *, plan_personas: list[str] | None = None) -> None:
        if persona in self.failed_personas:
            self.failed_personas.remove(persona)
        if persona not in self.completed_personas:
            self.completed_personas.append(persona)
        if self.status not in (EngagementStatus.CLOSED, EngagementStatus.FAILED):
            self.status = EngagementStatus.RUNNING
        plan = plan_personas if plan_personas is not None else self.planner_plan
        if plan and all(p in self._terminal_personas() for p in plan):
            self.status = EngagementStatus.CLOSED

    def record_persona_failed(self, persona: str, *, plan_personas: list[str] | None = None) -> None:
        if persona in self.completed_personas:
            self.completed_personas.remove(persona)
        if persona not in self.failed_personas:
            self.failed_personas.append(persona)
        if self.status not in (EngagementStatus.CLOSED, EngagementStatus.FAILED):
            self.status = EngagementStatus.RUNNING
        plan = plan_personas if plan_personas is not None else self.planner_plan
        if plan and all(p in self._terminal_personas() for p in plan):
            self.status = EngagementStatus.CLOSED

    def apply_planner_result(
        self,
        plan_personas: list[str],
        *,
        status: str,
        rationale: str = "",
        error: str = "",
        goal: str | None = None,
    ) -> None:
        self.planner_plan = list(plan_personas)
        self.planner_status = status
        self.planner_rationale = rationale
        self.planner_error = error
        if goal is not None:
            self.goal = goal
        if self.status == EngagementStatus.CREATED:
            self.status = EngagementStatus.PLANNING

    def fail_guardrail(self, reason: str) -> None:
        self.status = EngagementStatus.FAILED
        self.planner_error = reason
        self.planner_status = "failed"
