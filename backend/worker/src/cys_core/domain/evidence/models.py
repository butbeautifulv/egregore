from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TelemetryLevel = Literal["rich", "sparse", "metadata_only"]
ObservationKind = Literal[
    "host",
    "ip",
    "correlation_rule",
    "alert_id",
    "process",
    "account",
    "pipe",
    "pid",
    "event_text",
    "timestamp",
    "incident_key",
    "category",
]
DataGapReason = Literal["not_in_siem", "not_selected", "vendor_api_unavailable"]
FieldSource = Literal["incident", "linked_events", "recent_events", "search_events", "event_detail"]


class FieldAvailability(BaseModel):
    field_path: str
    present: bool
    source: FieldSource = "incident"
    event_uuids: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    obs_id: str
    kind: ObservationKind
    value: str
    source_tool: str
    source_path: str
    event_uuid: str | None = None


class DataGap(BaseModel):
    field: str
    reason: DataGapReason
    remediation: str = ""


class EvidenceManifest(BaseModel):
    telemetry_level: TelemetryLevel = "metadata_only"
    enrichment_sources: list[str] = Field(default_factory=list)
    required_external_sources: list[str] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    field_availability: list[FieldAvailability] = Field(default_factory=list)
    data_gaps: list[DataGap] = Field(default_factory=list)
    suggested_mitre_techniques: list[str] = Field(default_factory=list)
    max_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    def observation_index(self) -> dict[str, Observation]:
        return {obs.obs_id: obs for obs in self.observations}

    def observation_values(self) -> set[str]:
        return {obs.value.lower() for obs in self.observations if obs.value}


class EvidenceRef(BaseModel):
    obs_id: str
    excerpt: str = ""
    source_tool: str = ""
