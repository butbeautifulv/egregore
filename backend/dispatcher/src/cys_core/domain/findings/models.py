from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

# Plain str, not a closed Literal (MSP_BACKLOG.md §8.4 point 1) — persona names are
# profile-pack/catalog data, not something cys_core/domain should hardcode. Every
# real routing/lookup path already treats persona names as plain str validated (or
# not) against the live agent catalog (WorkerJob.persona, RoutingRule.personas,
# AgentCatalogEntry.name, persona_budget(), persona_clearance_for() are all str) —
# FindingEnvelope.agent was the one holdout, and FindingEnvelope itself has no
# real caller anywhere in src/ today.
WorkerAgentName = str


class ConductorStepResult(BaseModel):
    reply: str = ""
    plan_delta: dict[str, Any] = Field(default_factory=dict)
    spawn_requests: list[dict[str, Any]] = Field(default_factory=list)
    mode_recommendation: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning_steps: list[str] = Field(default_factory=list)
    plan_status: str = ""
    enough_data: bool = False
    remaining_steps: list[str] = Field(default_factory=list)
    task_completed: bool = False

    @field_validator("reasoning_steps", "remaining_steps", mode="before")
    @classmethod
    def _coerce_step_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, int):
            return [str(value)] if value else []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [str(item) for item in value]
        return []


class CriticResult(BaseModel):
    trust_score: float = Field(default=0.0, ge=0.0, le=1.0)
    finding_quality: str = ""
    issues_detected: list[str] = Field(default_factory=list)
    validated_claims: list[str] = Field(default_factory=list)
    rejected_claims: list[str] = Field(default_factory=list)
    reasoning_notes: list[str] = Field(default_factory=list)
    recommended_disposition: str = ""


class FindingEnvelope(BaseModel):
    agent: WorkerAgentName
    data: dict[str, Any]
    error: str | None = None
