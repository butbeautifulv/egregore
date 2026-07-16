from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

REASONING_STEP_TOOL = "reasoning_step"

SgrMode = Literal["off", "sgr_hybrid", "sgr_iron"]


class SchemaGuidedReasoningStep(BaseModel):
    """Per-step reasoning schema (ported from SGR ReasoningTool)."""

    reasoning_steps: list[str] = Field(
        description="Step-by-step reasoning (brief)",
        min_length=2,
        max_length=3,
    )
    current_situation: str = Field(max_length=300)
    plan_status: str = Field(max_length=150)
    enough_data: bool = False
    remaining_steps: list[str] = Field(default_factory=list, max_length=3)
    task_completed: bool


class SgrPolicy(BaseModel):
    enabled: bool = False
    mode: SgrMode = "off"
    require_before_action: bool = True
