from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RedTeamFinding(BaseModel):
    finding: str = ""
    severity: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    attack_path: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    affected_systems: list[str] = Field(default_factory=list)
    reproduction_steps: list[str] = Field(default_factory=list)
    recommended_remediation: list[str] = Field(default_factory=list)
    ttl: str = ""


class NetworkFinding(BaseModel):
    finding_type: str = ""
    severity: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    affected_assets: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ttl: str = ""


class SocFinding(BaseModel):
    incident_id: str = ""
    priority: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    timeline: list[str] = Field(default_factory=list)
    related_findings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ttl: str = ""


class ComplianceFinding(BaseModel):
    framework: str = ""
    control_id: str = ""
    compliance_status: str = ""
    evidence: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    risk_level: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    ttl: str = ""


class ConsultantFinding(BaseModel):
    topic: str = ""
    summary: str = ""
    risk_level: str = ""
    recommendations: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CriticResult(BaseModel):
    trust_score: float = Field(default=0.0, ge=0.0, le=1.0)
    finding_quality: str = ""
    issues_detected: list[str] = Field(default_factory=list)
    validated_claims: list[str] = Field(default_factory=list)
    rejected_claims: list[str] = Field(default_factory=list)
    reasoning_notes: list[str] = Field(default_factory=list)
    recommended_disposition: str = ""


class FindingEnvelope(BaseModel):
    agent: Literal["redteam", "network", "soc", "compliance", "consultant", "critic"]
    data: dict[str, Any]
    error: str | None = None
