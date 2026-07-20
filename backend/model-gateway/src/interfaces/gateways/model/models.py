from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelMessageIn(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    source: Literal["user", "tool", "agent_bus", "external", "catalog", "skill", "reflexion"] | None = None
    # tool_calls: populated on assistant messages that requested a tool call.
    # tool_call_id: populated on tool messages, correlating the result back to the call.
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_id: str = ""


class ModelInvokeRequest(BaseModel):
    persona: str
    system_prompt: str
    messages: list[ModelMessageIn] = Field(default_factory=list)
    system_prompt_digest: str = ""
    model: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    session_id: str = "default"
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: str | dict[str, Any] | None = None


class ModelInvokeResponse(BaseModel):
    success: bool
    content: str = ""
    refused: bool = False
    refusal_reason: str = ""
    model: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
