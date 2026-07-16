from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.runs.models import InteractionMode, RunContext
from cys_core.domain.runs.plan_models import ClarifyingQuestion, WorkPlan, WorkTodo


class RunStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    AWAITING_USER = "awaiting_user"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    CLOSED = "closed"


class RunState(BaseModel):
    run_context: RunContext
    goal: str = ""
    status: RunStatus = RunStatus.OPEN
    mode: InteractionMode | None = None
    plan: WorkPlan | None = None
    pending_questions: list[ClarifyingQuestion] = Field(default_factory=list)
    todos: list[WorkTodo] = Field(default_factory=list)
    last_result: dict[str, Any] = Field(default_factory=dict)
    step_count: int = 0
    context_summary: str = ""
    reasoning_notes: list[str] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    last_trace_verdict: dict[str, Any] = Field(default_factory=dict)
    trace_rerun_count: int = 0
