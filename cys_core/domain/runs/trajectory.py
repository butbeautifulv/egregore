from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


TraceEventType = Literal["model", "tool", "memory", "eval", "policy", "system"]


class TraceEvent(BaseModel):
    """Small, schema-stable trace event for run trajectories.

    This is intentionally generic. Consumers can interpret `payload` based on `type`.
    """

    type: TraceEventType
    name: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentTrajectory(BaseModel):
    """A sequence of trace events captured during a run/job/session."""

    trajectory_id: str
    context_id: str = ""
    tenant_id: str = "default"
    profile_id: str = ""
    persona: str = ""
    events: list[TraceEvent] = Field(default_factory=list)

    def record(self, event: TraceEvent) -> None:
        self.events.append(event)

