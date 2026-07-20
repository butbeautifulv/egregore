from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PromptRef(BaseModel):
    name: str
    label: str = "production"
    version: int | None = None


class ResolvedPrompt(BaseModel):
    text: str
    ref: PromptRef
    source: str = "filesystem"
    digest: str = ""


class TraceContext(BaseModel):
    trace_id: str = ""
    span_name: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


class JudgeRequest(BaseModel):
    rubric_ref: PromptRef
    input_text: str
    output_text: str
    context: dict[str, Any] = Field(default_factory=dict)


class JudgeResult(BaseModel):
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    verdict: str = ""
    reasoning: str = ""


class EvalScore(BaseModel):
    dataset: str
    item_id: str
    score: float = 0.0
    passed: bool = False
