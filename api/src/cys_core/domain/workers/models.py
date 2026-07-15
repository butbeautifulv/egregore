from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkerJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[WorkerJobStatus, frozenset[WorkerJobStatus]] = {
    WorkerJobStatus.PENDING: frozenset({WorkerJobStatus.RUNNING, WorkerJobStatus.FAILED}),
    WorkerJobStatus.RUNNING: frozenset(
        {WorkerJobStatus.COMPLETED, WorkerJobStatus.FAILED, WorkerJobStatus.AWAITING_APPROVAL}
    ),
    WorkerJobStatus.AWAITING_APPROVAL: frozenset({WorkerJobStatus.RUNNING, WorkerJobStatus.FAILED}),
    WorkerJobStatus.COMPLETED: frozenset(),
    WorkerJobStatus.FAILED: frozenset(),
}


def _default_max_tool_calls() -> int:
    return 50


class PersonaBudget(BaseModel):
    max_tokens: int
    max_cost_usd: float
    max_tool_calls: int = Field(default_factory=_default_max_tool_calls)


DEFAULT_BUDGET = PersonaBudget(max_tokens=40_000, max_cost_usd=2.0)


class WorkerJob(BaseModel):
    """Queued unit of work for an ephemeral worker."""

    job_id: str
    event_id: str
    persona: str
    playbook_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = ""
    tenant_id: str = "default"
    status: WorkerJobStatus = WorkerJobStatus.PENDING
    sandbox_id: str = ""
    feedback: str = ""
    depends_on_persona: str = ""
    max_tokens: int = 0
    max_cost_usd: float = 0.0
    max_tool_calls: int = 0

    def transition_to(self, status: WorkerJobStatus) -> None:
        if status == self.status:
            return
        allowed = _ALLOWED_TRANSITIONS.get(self.status, frozenset())
        if status not in allowed:
            raise ValueError(f"invalid job status transition: {self.status.value} -> {status.value}")
        self.status = status

    def apply_budget(self, budget: PersonaBudget) -> WorkerJob:
        return self.model_copy(
            update={
                "max_tokens": self.max_tokens or budget.max_tokens,
                "max_cost_usd": self.max_cost_usd or budget.max_cost_usd,
                "max_tool_calls": self.max_tool_calls or budget.max_tool_calls,
            }
        )


class SandboxCredentials(BaseModel):
    """Credentials returned when a sandbox is provisioned."""

    sandbox_id: str
    endpoint: str = ""
    token: str = ""


class PendingHitlAction(BaseModel):
    """Tool call waiting for human approval."""

    job_id: str
    session_id: str
    persona: str
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = ""
    approval_id: str = ""


class JobResumeRequest(BaseModel):
    """Resume payload for a paused worker job."""

    decision: str  # approve | reject | edit
    edited_args: dict[str, Any] = Field(default_factory=dict)
    approval_id: str = ""
    actor: str = "operator"


class RunResult(BaseModel):
    """Outcome of a single worker run."""

    job_id: str
    persona: str
    success: bool
    finding: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    sandbox_id: str = ""


class WorkloadSpec(BaseModel):
    persona: str
    engagement_id: str
    image: str = "egregore-agent:latest"
    policy: str = "default"


class WorkloadHandle(BaseModel):
    workload_id: str
    sandbox_id: str
    endpoint: str = ""
