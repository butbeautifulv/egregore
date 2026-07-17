from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EngagementStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    ENQUEUED = "enqueued"
    RUNNING = "running"
    CLOSED = "closed"
    FAILED = "failed"

    def is_terminal(self) -> bool:
        return self in (EngagementStatus.CLOSED, EngagementStatus.FAILED)


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

    def is_pipeline_staged(self) -> bool:
        return self.effective_execution_mode() == ExecutionMode.STAGED and len(self.personas) > 1


class EngagementRequest(BaseModel):
    profile_id: str = "cybersec-soc"
    domain_id: str = ""
    workspace_id: str = ""
    goal: str
    mode: EngagementMode = EngagementMode.ASYNC
    plan_strategy: PlanStrategy = PlanStrategy.META_LLM
    input: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = "default"
    correlation_id: str = ""
    intent_mode: str = "auto"
    skip_dispatch: bool = False


class Engagement(BaseModel):
    id: str
    tenant_id: str = "default"
    profile_id: str = "cybersec-soc"
    domain_id: str = ""
    workspace_id: str = ""
    goal: str
    mode: EngagementMode = EngagementMode.ASYNC
    status: EngagementStatus = EngagementStatus.CREATED
    correlation_id: str = ""
    plan_strategy: PlanStrategy = PlanStrategy.META_LLM
    job_ids: list[str] = Field(default_factory=list)
    completed_personas: list[str] = Field(default_factory=list)
    failed_personas: list[str] = Field(default_factory=list)
    findings_summary: list[dict[str, Any]] = Field(default_factory=list)
    evidence_manifests: dict[str, Any] = Field(default_factory=dict)
    planner_plan: list[str] | None = None
    planner_status: str | None = None
    planner_rationale: str = ""
    planner_error: str = ""
    planner_sub_goals: dict[str, str] = Field(default_factory=dict)
    planner_depends_on: dict[str, list[str]] = Field(default_factory=dict)
    execution_mode: ExecutionMode | None = None
    synthesis_persona: str | None = None
    synthesis_status: SynthesisStatus | None = None
    final_report: dict[str, Any] | None = None
    planning_started_at: str | None = None
    pending_follow_ups: list[dict[str, Any]] = Field(default_factory=list)
    context_summary: str = ""
    follow_up_spawn_count: int = 0
    follow_up_spawned_job_ids: list[str] = Field(default_factory=list)
    follow_up_iteration: int = 0
    follow_up_goal: str = ""
    active_follow_up_id: str | None = None
    plan_history: list[dict[str, Any]] = Field(default_factory=list)
    intake: dict[str, Any] = Field(default_factory=dict)

    def reopen_for_follow_up(self) -> None:
        if self.status == EngagementStatus.CLOSED:
            self.status = EngagementStatus.RUNNING

    def close_after_follow_up(self) -> None:
        self.status = EngagementStatus.CLOSED
        self.active_follow_up_id = None

    def close_after_initial_qa(self) -> None:
        self.status = EngagementStatus.CLOSED
        self.active_follow_up_id = None
        self.synthesis_status = SynthesisStatus.SKIPPED

    def begin_follow_up_planning(self, *, operator_message: str, follow_up_id: str) -> None:
        from datetime import datetime, timezone

        if self.planner_plan:
            self.plan_history.append(
                {
                    "iteration": self.follow_up_iteration,
                    "goal": self.follow_up_goal or self.goal,
                    "planner_plan": list(self.planner_plan),
                    "planner_rationale": self.planner_rationale,
                    "planner_sub_goals": dict(self.planner_sub_goals),
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        self.follow_up_iteration += 1
        self.follow_up_goal = operator_message.strip()
        self.active_follow_up_id = follow_up_id
        self.reopen_for_follow_up()
        synth = self.synthesis_persona
        self.completed_personas = [p for p in self.completed_personas if p == synth]
        self.failed_personas = []
        self.synthesis_status = SynthesisStatus.PENDING
        self.planner_status = "planning"
        self.planner_plan = None
        self.planner_rationale = ""
        self.planner_error = ""
        self.planner_sub_goals = {}
        self.planner_depends_on = {}
        self.planning_started_at = datetime.now(timezone.utc).isoformat()
        self.status = EngagementStatus.PLANNING

    def begin_planning(self, goal: str | None = None) -> None:
        from datetime import datetime, timezone

        if goal is not None:
            self.goal = goal
        if self.status == EngagementStatus.CREATED:
            self.status = EngagementStatus.PLANNING
        self.planner_status = "planning"
        self.planner_plan = None
        self.planner_rationale = ""
        self.planner_error = ""
        self.planner_sub_goals = {}
        self.planner_depends_on = {}
        self.planning_started_at = datetime.now(timezone.utc).isoformat()

    def mark_enqueued(self, job_ids: list[str]) -> None:
        self.status = EngagementStatus.ENQUEUED if job_ids else EngagementStatus.PLANNING
        self.job_ids = list(job_ids)

    def _terminal_personas(self) -> set[str]:
        return set(self.completed_personas) | set(self.failed_personas)

    def specialists_terminal(self, *, plan_personas: list[str] | None = None) -> bool:
        return self._specialists_terminal(plan_personas=plan_personas)

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

    def _reconcile_personas_from_findings(self) -> None:
        """Align completed/failed with findings_summary after salvage or synthesis."""
        synth = self.synthesis_persona
        finding_personas = {
            str(item.get("persona", ""))
            for item in self.findings_summary
            if isinstance(item, dict) and item.get("persona") and item.get("persona") != synth
        }
        for persona in finding_personas:
            if persona in self.failed_personas:
                self.failed_personas.remove(persona)
            if persona not in self.completed_personas:
                self.completed_personas.append(persona)

    def complete_synthesis(self, report: dict[str, Any]) -> None:
        self.final_report = report
        self.synthesis_status = SynthesisStatus.DONE
        self._reconcile_personas_from_findings()
        self.status = EngagementStatus.CLOSED

    def fail_synthesis(self, reason: str, *, degraded: bool = False) -> None:
        self.synthesis_status = SynthesisStatus.DONE
        self.planner_error = reason
        specialist_findings = [
            item
            for item in self.findings_summary
            if isinstance(item, dict)
            and item.get("persona")
            and item.get("persona") != self.synthesis_persona
        ]
        if degraded and specialist_findings:
            self._reconcile_personas_from_findings()
            self.status = EngagementStatus.CLOSED
            if self.final_report is None:
                self.final_report = {
                    "kind": "synthesis",
                    "title": "Degraded synthesis",
                    "summary": reason,
                    "degraded": True,
                    "provenance": [
                        {
                            "persona": str(item.get("persona", "")),
                            "job_id": str(item.get("job_id", "")),
                            "status": "completed",
                        }
                        for item in specialist_findings
                        if isinstance(item, dict) and item.get("persona")
                    ],
                }
        else:
            self.status = EngagementStatus.FAILED

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
        planner_sub_goals: dict[str, str] | None = None,
        planner_depends_on: dict[str, list[str]] | None = None,
    ) -> None:
        self.planner_plan = list(plan_personas)
        self.planner_status = status
        self.planner_rationale = rationale
        self.planner_error = error
        self.execution_mode = execution_mode
        self.synthesis_persona = synthesis_persona
        if planner_sub_goals is not None:
            self.planner_sub_goals = dict(planner_sub_goals)
        if planner_depends_on is not None:
            self.planner_depends_on = {
                str(key): [str(item) for item in value]
                for key, value in planner_depends_on.items()
            }
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
