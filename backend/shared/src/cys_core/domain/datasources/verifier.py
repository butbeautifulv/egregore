from __future__ import annotations

from pydantic import BaseModel, Field


class VerifierScoreDecision(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    decision: str = Field(description="accept | rerun | reject")
    rationale: str = ""


class VerifierPrompts(BaseModel):
    critique: str = "Critique the trajectory for policy violations and missing evidence."
    scoring: str = "Return JSON {score, decision, rationale} with decision in accept|rerun|reject."
    boundary_semantics: str = "score < 0.55 => rerun; score >= 0.55 => accept"
