from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

MemoryType = Literal["finding", "pending_finding", "ioc", "lesson", "preference", "conversation", "intake"]
InvestigationStatus = Literal["open", "in_progress", "closed"]
PlannerStatus = Literal["planning", "ok", "fallback", "error"]


class MemoryScope(BaseModel):
    tenant_id: str
    investigation_id: str
    workspace_id: str = ""
    persona: str | None = None


class MemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: f"mem-{uuid4().hex[:12]}")
    scope: MemoryScope
    content: str
    memory_type: MemoryType = "finding"
    source_agent: str = ""
    source_job_id: str = ""
    trust_score: float = 1.0
    checksum: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InvestigationState(BaseModel):
    """Deprecated: use ``Engagement`` as the canonical investigation aggregate."""

    investigation_id: str
    tenant_id: str
    goal: str = ""
    status: InvestigationStatus = "open"
    completed_personas: list[str] = Field(default_factory=list)
    findings_summary: list[dict[str, Any]] = Field(default_factory=list)
    planner_plan: list[str] | None = None
    planner_status: PlannerStatus | None = None
    planner_rationale: str = ""
    planner_error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
