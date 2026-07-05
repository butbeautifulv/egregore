from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolInvokeRequest(BaseModel):
    """Gateway invoke request from worker sandbox."""

    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    persona: str
    sandbox_id: str
    job_id: str = ""
    correlation_id: str = ""
    profile_id: str = "cybersec-soc"


class ToolInvokeResponse(BaseModel):
    """Sanitized gateway response returned to the agent runtime."""

    success: bool
    tool_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    sanitized_payload: str = ""
    error: str = ""
