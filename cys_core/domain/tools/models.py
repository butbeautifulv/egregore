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


class ToolInvokeResult(BaseModel):
    success: bool
    tool_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    sanitized_payload: str = ""
    error: str = ""
    stub_result: StubToolResult | None = None
