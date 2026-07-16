from __future__ import annotations

from cys_core.domain.tools.models import ToolInvokeCommand, ToolInvokeResult
from interfaces.gateways.tool.models import ToolInvokeRequest, ToolInvokeResponse


def to_command(request: ToolInvokeRequest) -> ToolInvokeCommand:
    return ToolInvokeCommand(
        tool_name=request.tool_name,
        args=request.args,
        persona=request.persona,
        sandbox_id=request.sandbox_id,
        job_id=request.job_id,
        correlation_id=request.correlation_id,
        profile_id=request.profile_id,
        workspace_id=request.workspace_id,
        organization_id=request.organization_id,
        user_id=request.user_id,
    )


def to_response(result: ToolInvokeResult) -> ToolInvokeResponse:
    return ToolInvokeResponse(
        success=result.success,
        tool_name=result.tool_name,
        data=result.data,
        sanitized_payload=result.sanitized_payload,
        error=result.error,
    )
