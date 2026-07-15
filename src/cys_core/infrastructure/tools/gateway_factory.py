from __future__ import annotations

from cys_core.application.ports.tool_gateway import ToolExecutionGatewayPort

_gateway: ToolExecutionGatewayPort | None = None


def configure_tool_execution_gateway(gateway: ToolExecutionGatewayPort) -> None:
    global _gateway
    _gateway = gateway


def get_tool_execution_gateway() -> ToolExecutionGatewayPort:
    if _gateway is None:
        raise RuntimeError("Tool execution gateway not configured — wire via bootstrap Container")
    return _gateway


def reset_tool_execution_gateway_cache() -> None:
    global _gateway
    _gateway = None
