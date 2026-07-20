from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProvenanceRef(BaseModel):
    persona: str
    job_id: str = ""
    obs_ids: list[str] = Field(default_factory=list)
    status: str = "completed"


class OutcomeSection(BaseModel):
    title: str
    body: str
    items: list[str] = Field(default_factory=list)


class OperatorOutcome(BaseModel):
    kind: Literal["advisory", "investigation", "synthesis"] = "advisory"
    title: str = ""
    summary: str
    sections: list[OutcomeSection] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    provenance: list[ProvenanceRef] = Field(default_factory=list)
    confidence: float = 0.5
    risk_level: str | None = None
    degraded: bool = False
    references: list[str] = Field(default_factory=list)

    def to_final_report(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)
