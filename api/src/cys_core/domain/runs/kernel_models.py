from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.runs.trajectory import AgentTrajectory


class RunKernelMode(str, Enum):
    INTERACTIVE = "interactive"
    WORKER = "worker"


class RunKernelRequest(BaseModel):
    run_id: str
    session_id: str
    persona: str
    profile_id: str
    tenant_id: str
    investigation_id: str
    prompt: str
    mode: RunKernelMode
    correlation_id: str = ""
    max_tokens: int | None = None
    max_cost_usd: float | None = None
    max_tool_calls: int | None = None
    sandbox_tools: list[Any] | None = None
    job_id: str | None = None
    event_id: str | None = None
    sandbox_id: str | None = None
    memory_entries_loaded: int = 0


class RunKernelResult(BaseModel):
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    trajectory: AgentTrajectory
    error: str = ""
