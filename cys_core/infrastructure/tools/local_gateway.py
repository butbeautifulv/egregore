from __future__ import annotations

from cys_core.application.ports.tool_gateway import ToolExecutionGatewayPort
from cys_core.application.ports.tool_invoke import ToolInvokePort
from cys_core.domain.tools.models import StubToolResult, ToolInvokeCommand, ToolInvokeResult


class LocalToolExecutionGateway:
    """In-process gateway delegating to the wired tool invoke port."""

    def __init__(self, invoke_tool: ToolInvokePort) -> None:
        self._invoke_tool = invoke_tool

    def invoke(self, command: ToolInvokeCommand) -> ToolInvokeResult:
        result = self._invoke_tool.execute(command)
        stub = None
        if result.data.get("status") == "simulated" or result.data.get("stub"):
            stub = StubToolResult(tool_name=command.tool_name, simulated=True, note=str(result.data.get("note", "")))
        if stub is not None:
            return result.model_copy(update={"stub_result": stub})
        return result


def build_local_tool_execution_gateway(invoke_tool: ToolInvokePort) -> ToolExecutionGatewayPort:
    return LocalToolExecutionGateway(invoke_tool)
