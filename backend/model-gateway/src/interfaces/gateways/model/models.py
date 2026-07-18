from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelMessageIn(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    source: Literal["user", "tool", "agent_bus", "external", "catalog", "skill", "reflexion"] | None = None


class ModelInvokeRequest(BaseModel):
    persona: str
    system_prompt: str
    messages: list[ModelMessageIn] = Field(default_factory=list)
    system_prompt_digest: str = ""
    model: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    session_id: str = "default"


class ModelInvokeResponse(BaseModel):
    success: bool
    content: str = ""
    refused: bool = False
    refusal_reason: str = ""
    model: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
