from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PendingApproval(BaseModel):
    trust_score: float
    findings_count: int
    high_severity: list[dict[str, Any]] = Field(default_factory=list)
    message: str


class AssessmentReport(BaseModel):
    status: Literal["published", "rejected"]
    session_id: str | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    critic_result: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    reason: str | None = None
    pending_approval: dict[str, Any] | None = None

