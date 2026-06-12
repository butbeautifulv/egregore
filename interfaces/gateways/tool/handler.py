from __future__ import annotations

from cys_core.application.use_cases.invoke_tool import InvokeTool
from cys_core.observability.metrics import metrics
from cys_core.registry.mcp_tools import require_sandbox
from cys_core.registry.tools import tool_registry
from interfaces.gateways.tool.adapters import invoke_adapter
from interfaces.gateways.tool.audit import record_tool_invocation
from interfaces.gateways.tool.models import ToolInvokeRequest, ToolInvokeResponse
from interfaces.gateways.tool.policy import check_tool_chain
from interfaces.gateways.tool.sanitize import sanitize_tool_output_or_raise


def _invoke_tool_use_case() -> InvokeTool:
    return InvokeTool(
        require_sandbox=require_sandbox,
        check_tool_chain=check_tool_chain,
        invoke_adapter=invoke_adapter,
        tool_registry=tool_registry,
        sanitize_tool_output_or_raise=sanitize_tool_output_or_raise,
        record_tool_invocation=record_tool_invocation,
        record_tool_metric=lambda name, ok: metrics.record_tool_invocation(name, success=ok),
    )


def invoke_tool(request: ToolInvokeRequest) -> ToolInvokeResponse:
    """Authorize, execute tool backend, sanitize response, audit."""
    return _invoke_tool_use_case().execute(request)
