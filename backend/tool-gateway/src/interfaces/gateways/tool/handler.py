from __future__ import annotations

from bootstrap.container import get_container
from cys_core.domain.security.auth_models import AuthClaims
from interfaces.gateways.tool.mappers import to_command, to_response
from interfaces.gateways.tool.models import ToolInvokeRequest, ToolInvokeResponse


async def invoke_tool(
    request: ToolInvokeRequest,
    *,
    auth: AuthClaims | None = None,
    workspace_id: str = "",
) -> ToolInvokeResponse:
    """HTTP/local adapter: map transport DTOs and delegate to ToolExecutionGatewayPort."""
    enriched = request.model_copy(
        update={
            "workspace_id": request.workspace_id or workspace_id,
            "organization_id": request.organization_id or (auth.organization_id if auth else ""),
            "user_id": request.user_id or (auth.sub if auth else ""),
        }
    )
    result = await get_container().get_tool_execution_gateway().invoke(to_command(enriched))
    return to_response(result)
