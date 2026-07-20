from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ToolStatus(str, Enum):
    REAL = "real"
    SIMULATED = "simulated"
    STUB = "stub"
    DISABLED = "disabled"


class ToolDefinitionView(BaseModel):
    """Provider-facing tool metadata for attach-time filtering and docs."""

    name: str
    description: str = ""
    status: ToolStatus = ToolStatus.REAL
    module: str = "builtin"
    datasource_id: str = ""
    json_schema: dict[str, Any] = Field(default_factory=dict)


class StubToolResult(BaseModel):
    """Marker for stub/simulated tool responses in traces."""

    stub: bool = True
    simulated: bool = False
    tool_name: str = ""
    note: str = ""


class ToolInvokeCommand(BaseModel):
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    persona: str
    sandbox_id: str
    profile_id: str = "cybersec-soc"
    job_id: str = ""
    correlation_id: str = ""
    workspace_id: str = ""
    organization_id: str = ""
    user_id: str = ""
    # Signed, short-lived proof that this call really originates from the
    # sandboxed run it claims to (mint_sandbox_token/verify_sandbox_token,
    # cys_core.domain.security.sandbox_tokens) — minted but never verified
    # anywhere until docs/MSP_BACKLOG.md §37 wired it here.
    sandbox_token: str = ""
    # Presented on retry after a human approves a previously-refused high-risk
    # call — InvokeTool's check_hitl skips re-classification when this matches
    # the exact tool_name/args the token was minted for (mint_approval_token/
    # verify_approval_token, cys_core.domain.security.approval_tokens).
    # docs/MSP_BACKLOG.md §35/§58.
    approval_token: str = ""


class ToolInvokeResult(BaseModel):
    success: bool
    tool_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    sanitized_payload: str = ""
    error: str = ""
    stub_result: StubToolResult | None = None
    # Set when InvokeTool refused to execute pending human approval (§35/§58) —
    # error is "hitl_required" in that case, approval_token is what the caller
    # must present on retry once a human approves.
    hitl_required: bool = False
    risk_level: str = ""
    approval_token: str = ""
