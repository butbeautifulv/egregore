from __future__ import annotations

from bootstrap.container import get_container
from interfaces.gateways.tool.mappers import to_command, to_response
from interfaces.gateways.tool.models import ToolInvokeRequest, ToolInvokeResponse


def invoke_tool(request: ToolInvokeRequest) -> ToolInvokeResponse:
    """HTTP/local adapter: map transport DTOs and delegate to ToolExecutionGatewayPort."""
    result = get_container().get_tool_execution_gateway().invoke(to_command(request))
    return to_response(result)
