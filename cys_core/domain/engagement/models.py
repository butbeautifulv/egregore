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


class ExecutionMode(StrEnum):
    PARALLEL = "parallel"
    STAGED = "staged"


class SynthesisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"


class EngagementPlan(BaseModel):
    personas: list[str] = Field(default_factory=list)
    sub_goals: dict[str, str] = Field(default_factory=dict)
    depends_on: dict[str, list[str]] = Field(default_factory=dict)
    plan_id: str = ""
    strategy: PlanStrategy = PlanStrategy.DECLARATIVE
    rationale: str = ""
    reasoning_steps: list[str] = Field(default_factory=list)
    plan_status: str = ""
    execution_mode: ExecutionMode | None = None
    synthesis_persona: str | None = None

    def effective_execution_mode(self) -> ExecutionMode:
        if self.execution_mode is not None:
            return self.execution_mode
        if len(self.personas) > 1:
            return ExecutionMode.STAGED
        return ExecutionMode.PARALLEL


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
    evidence_manifests: dict[str, Any] = Field(default_factory=dict)
    planner_plan: list[str] | None = None
    planner_status: str | None = None
    planner_rationale: str = ""
    planner_error: str = ""
    execution_mode: ExecutionMode | None = None
    synthesis_persona: str | None = None
    synthesis_status: SynthesisStatus | None = None
    final_report: dict[str, Any] | None = None

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

    def _specialists_terminal(self, *, plan_personas: list[str] | None = None) -> bool:
        plan = plan_personas if plan_personas is not None else self.planner_plan
        if not plan:
            return False
        return all(p in self._terminal_personas() for p in plan)

    def _maybe_close(self, *, plan_personas: list[str] | None = None) -> None:
        if not self._specialists_terminal(plan_personas=plan_personas):
            return
        if self.synthesis_status in (SynthesisStatus.PENDING, SynthesisStatus.RUNNING):
            return
        self.status = EngagementStatus.CLOSED

    def record_persona_completed(self, persona: str, *, plan_personas: list[str] | None = None) -> None:
        if self.synthesis_persona and persona == self.synthesis_persona:
            return
        if persona in self.failed_personas:
            self.failed_personas.remove(persona)
        if persona not in self.completed_personas:
            self.completed_personas.append(persona)
        if self.status not in (EngagementStatus.CLOSED, EngagementStatus.FAILED):
            self.status = EngagementStatus.RUNNING
        self._maybe_close(plan_personas=plan_personas)

    def record_persona_failed(self, persona: str, *, plan_personas: list[str] | None = None) -> None:
        if self.synthesis_persona and persona == self.synthesis_persona:
            return
        if persona in self.completed_personas:
            self.completed_personas.remove(persona)
        if persona not in self.failed_personas:
            self.failed_personas.append(persona)
        if self.status not in (EngagementStatus.CLOSED, EngagementStatus.FAILED):
            self.status = EngagementStatus.RUNNING
        self._maybe_close(plan_personas=plan_personas)

    def complete_synthesis(self, report: dict[str, Any]) -> None:
        self.final_report = report
        self.synthesis_status = SynthesisStatus.DONE
        self.status = EngagementStatus.CLOSED

    def fail_synthesis(self, reason: str) -> None:
        self.synthesis_status = SynthesisStatus.DONE
        self.status = EngagementStatus.FAILED
        self.planner_error = reason

    def apply_planner_result(
        self,
        plan_personas: list[str],
        *,
        status: str,
        rationale: str = "",
        error: str = "",
        goal: str | None = None,
        execution_mode: ExecutionMode | None = None,
        synthesis_persona: str | None = None,
    ) -> None:
        self.planner_plan = list(plan_personas)
        self.planner_status = status
        self.planner_rationale = rationale
        self.planner_error = error
        self.execution_mode = execution_mode
        self.synthesis_persona = synthesis_persona
        if synthesis_persona and synthesis_persona not in plan_personas:
            self.synthesis_status = SynthesisStatus.PENDING
        else:
            self.synthesis_status = SynthesisStatus.SKIPPED
        if goal is not None:
            self.goal = goal
        if self.status == EngagementStatus.CREATED:
            self.status = EngagementStatus.PLANNING

    def fail_guardrail(self, reason: str) -> None:
        self.status = EngagementStatus.FAILED
        self.planner_error = reason
        self.planner_status = "failed"
