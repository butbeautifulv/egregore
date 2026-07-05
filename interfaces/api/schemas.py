from __future__ import annotations

from pydantic import BaseModel, Field


class InvestigationSummaryOut(BaseModel):
    investigation_id: str
    tenant_id: str
    goal: str = ""
    status: str
    completed_personas: list[str] = Field(default_factory=list)


class InvestigationDetailOut(InvestigationSummaryOut):
    latest_phase: str | None = None
    planner_plan: list[str] | None = None
    planner_status: str | None = None
    planner_rationale: str = ""
    planner_error: str = ""
    findings_summary: list[dict] = Field(default_factory=list)


class JobSummaryOut(BaseModel):
    job_id: str
    persona: str
    status: str
    session_id: str
    correlation_id: str = ""
    event_id: str = ""
    created_at: str = ""


class InvestigationsListOut(BaseModel):
    investigations: list[InvestigationSummaryOut]


class InvestigationJobsOut(BaseModel):
    jobs: list[JobSummaryOut]
