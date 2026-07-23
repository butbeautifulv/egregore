from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from cys_core.domain.evidence.models import DataGap, EvidenceRef

# SOC-specific Finding shapes, extracted out of cys_core/domain/findings/models.py
# (MSP_BACKLOG.md §8.4 point 2) so core keeps only the generic FindingEnvelope —
# cys_core/domain must have zero knowledge of any one product pack's finding
# schemas. schema_name resolution stays in cys_core/registry/schemas.py, which
# only registers these when the active profile pack is cybersec-soc.

AttackPhase = Literal[
    "recon",
    "weaponization",
    "delivery",
    "exploitation",
    "installation",
    "c2",
    "actions",
]


class KillChainFields(BaseModel):
    """Shared kill-chain / ATT&CK overlay for cybersec-soc findings."""

    attack_phase: AttackPhase | None = None
    mitre_tactics: list[str] = Field(default_factory=list)
    mitre_techniques: list[str] = Field(default_factory=list)


class RedTeamFinding(KillChainFields):
    finding: str = ""
    severity: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    attack_path: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    affected_systems: list[str] = Field(default_factory=list)
    reproduction_steps: list[str] = Field(default_factory=list)
    recommended_remediation: list[str] = Field(default_factory=list)
    ttl: str = ""


class NetworkFinding(KillChainFields):
    finding_type: str = ""
    severity: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    affected_assets: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ttl: str = ""


class SocFinding(KillChainFields):
    incident_id: str = ""
    priority: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    timeline: list[str] = Field(default_factory=list)
    related_findings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    data_gaps: list[DataGap] = Field(default_factory=list)
    telemetry_level: Literal["rich", "sparse", "metadata_only"] = "metadata_only"
    ttl: str = ""

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            out: list[Any] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    out.append({"obs_id": item.strip(), "excerpt": item.strip()})
                elif isinstance(item, dict):
                    out.append(item)
            return out
        return []

    @field_validator("data_gaps", mode="before")
    @classmethod
    def _coerce_data_gaps(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            out: list[Any] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    out.append({"field": item.strip(), "reason": "not_in_siem", "remediation": ""})
                elif isinstance(item, dict):
                    out.append(item)
            return out
        return []


class ComplianceFinding(KillChainFields):
    framework: str = ""
    control_id: str = ""
    compliance_status: str = ""
    evidence: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    risk_level: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    ttl: str = ""


class ConsultantFinding(KillChainFields):
    topic: str = ""
    summary: str = ""
    risk_level: str = ""
    recommendations: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class IntelFinding(KillChainFields):
    actor_profile: str = ""
    ttps: list[str] = Field(default_factory=list)
    iocs: list[str] = Field(default_factory=list)
    recon_indicators: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    ttl: str = ""


class HunterFinding(KillChainFields):
    hypothesis: str = ""
    technique_ids: list[str] = Field(default_factory=list)
    hunt_status: str = ""
    evidence: list[str] = Field(default_factory=list)
    detection_gaps: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ttl: str = ""


class IdentityFinding(KillChainFields):
    identity_asset: str = ""
    attack_path: list[str] = Field(default_factory=list)
    credential_indicators: list[str] = Field(default_factory=list)
    lateral_movement_stage: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    ttl: str = ""


class DfirFinding(KillChainFields):
    artifacts: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)
    containment_status: str = ""
    eradication_steps: list[str] = Field(default_factory=list)
    forensic_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    ttl: str = ""


class CloudFinding(KillChainFields):
    cloud_provider: str = ""
    resource_id: str = ""
    misconfig_type: str = ""
    blast_radius: str = ""
    remediation: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    ttl: str = ""


class PurpleFinding(KillChainFields):
    kill_chain_phases_completed: list[str] = Field(default_factory=list)
    attack_coverage_map: dict[str, list[str]] = Field(default_factory=dict)
    detection_gaps: list[str] = Field(default_factory=list)
    recommended_atomic_tests: list[str] = Field(default_factory=list)
    d3fend_controls: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    ttl: str = ""
