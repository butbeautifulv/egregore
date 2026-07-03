from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from cys_core.domain.runs.models import RunContext
from cys_core.domain.runs.trajectory import AgentTrajectory


class RunKernelRequest(BaseModel):
    """Normalized request for both interactive and worker execution paths."""

    context: RunContext
    persona: str
    user_input: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class RunKernelResult(BaseModel):
    """Normalized result with an optional unified trajectory."""

    status: str = "ok"
    output: dict[str, Any] = Field(default_factory=dict)
    trajectory: AgentTrajectory | None = None


class RunKernelPort(Protocol):
    async def run(self, request: RunKernelRequest) -> RunKernelResult: ...

