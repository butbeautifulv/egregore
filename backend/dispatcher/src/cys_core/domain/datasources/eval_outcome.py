from __future__ import annotations

from pydantic import BaseModel, Field


class OutcomeEvalConfig(BaseModel):
    reward_basis: str = "assertions"
    evaluators_enabled: list[str] = Field(default_factory=lambda: ["outcome", "communicate"])
    min_pass_score: float = 0.5


class OutcomeEvalResult(BaseModel):
    case_id: str
    passed: bool
    score: float
    assertions: list[str] = Field(default_factory=list)
    communicate_ok: bool = True
