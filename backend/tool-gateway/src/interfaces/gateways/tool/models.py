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
    workspace_id: str = ""
    organization_id: str = ""
    user_id: str = ""
    sandbox_token: str = ""
    approval_token: str = ""


class ToolInvokeResponse(BaseModel):
    """Sanitized gateway response returned to the agent runtime."""

    success: bool
    tool_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    sanitized_payload: str = ""
    error: str = ""
    hitl_required: bool = False
    risk_level: str = ""
    approval_token: str = ""
