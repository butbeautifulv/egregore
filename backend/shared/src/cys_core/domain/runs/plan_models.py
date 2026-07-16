from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from cys_core.domain.engagement.models import ExecutionMode


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkTodo(BaseModel):
    id: str
    content: str
    status: TodoStatus = TodoStatus.PENDING
    assigned_persona: str = ""
    depends_on: list[str] = Field(default_factory=list)


class ClarifyingQuestion(BaseModel):
    id: str
    question: str
    required: bool = True


class WorkPlan(BaseModel):
    questions: list[ClarifyingQuestion] = Field(default_factory=list)
    todos: list[WorkTodo] = Field(default_factory=list)
    proposed_workers: list[str] = Field(default_factory=list)
    rationale: str = ""
    awaiting_user_input: bool = False
    reasoning_steps: list[str] = Field(default_factory=list)
    plan_status: str = ""
    enough_data: bool = False
    remaining_steps: list[str] = Field(default_factory=list)


class PlanApproval(BaseModel):
    decision: Literal["approve", "reject", "edit"]
    edited_plan: WorkPlan | None = None
    actor: str = "operator"


class InvestigationPlanStep(BaseModel):
    """SGR-aligned plan step metadata for investigations."""

    plan_status: str = ""
    remaining_steps: list[str] = Field(default_factory=list)
    enough_data: bool = False


class EngagementPlannerOutput(BaseModel):
    """Structured meta-LLM planner response for engagement.start."""

    personas: list[str] = Field(default_factory=list)
    sub_goals: dict[str, str] = Field(default_factory=dict)
    rationale: str = ""
    reasoning_steps: list[str] = Field(default_factory=list)
    plan_status: str = ""
    execution_mode: ExecutionMode | None = None
    synthesis_persona: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_sub_goals(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        sub_goals = data.get("sub_goals")
        if not isinstance(sub_goals, list):
            return data
        personas = data.get("personas") or []
        if personas and len(personas) == len(sub_goals):
            data["sub_goals"] = dict(zip(personas, sub_goals, strict=False))
        else:
            data["sub_goals"] = {f"goal_{i}": goal for i, goal in enumerate(sub_goals)}
        return data


class GeneratePlanPayload(BaseModel):
    """Initial investigation plan (SGR GeneratePlanTool analogue)."""

    reasoning_steps: list[str] = Field(min_length=2, max_length=3)
    plan_status: str = Field(max_length=150)
    personas: list[str] = Field(default_factory=list)
    sub_goals: list[str] = Field(default_factory=list)
    rationale: str = ""


class AdaptPlanPayload(BaseModel):
    """Plan revision after new findings (SGR AdaptPlanTool analogue)."""

    reasoning_steps: list[str] = Field(min_length=2, max_length=3)
    plan_status: str = Field(max_length=150)
    remaining_steps: list[str] = Field(default_factory=list, max_length=3)
    plan_delta: WorkPlan | None = None
    enough_data: bool = False
