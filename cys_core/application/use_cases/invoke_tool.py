from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from interfaces.gateways.tool.models import ToolInvokeRequest, ToolInvokeResponse
from interfaces.gateways.tool.policy import ToolChainDepthExceeded


class ToolRegistryPort(Protocol):
    def get(self, name: str) -> Any: ...


def _normalize_raw_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {"raw": raw}
        return {"raw": raw}
    return {"result": raw}


class InvokeTool:
    """Authorize, execute tool backend, sanitize response, audit."""

    def __init__(
        self,
        *,
        require_sandbox: Callable[[str], None],
        check_tool_chain: Callable[[ToolInvokeRequest], None],
        invoke_adapter: Callable[[str, dict[str, Any]], dict[str, Any] | None],
        tool_registry: ToolRegistryPort,
        sanitize_tool_output_or_raise: Callable[[dict[str, Any]], dict[str, Any]],
        record_tool_invocation: Callable[[ToolInvokeRequest, ToolInvokeResponse], None],
        record_tool_metric: Callable[[str, bool], None] | None = None,
    ) -> None:
        self.require_sandbox = require_sandbox
        self.check_tool_chain = check_tool_chain
        self.invoke_adapter = invoke_adapter
        self.tool_registry = tool_registry
        self.sanitize_tool_output_or_raise = sanitize_tool_output_or_raise
        self.record_tool_invocation = record_tool_invocation
        self.record_tool_metric = record_tool_metric or (lambda _name, _ok: None)

    def _execute_tool(self, request: ToolInvokeRequest) -> dict[str, Any]:
        adapter_result = self.invoke_adapter(request.tool_name, request.args)
        if adapter_result is not None:
            return adapter_result
        base = self.tool_registry.get(request.tool_name)
        raw = base.invoke(request.args)
        return _normalize_raw_result(raw)

    def execute(self, request: ToolInvokeRequest) -> ToolInvokeResponse:
        try:
            self.require_sandbox(request.sandbox_id)
            self.check_tool_chain(request)
            data = self._execute_tool(request)
            sanitized = self.sanitize_tool_output_or_raise(data)
            response = ToolInvokeResponse(
                success=True,
                tool_name=request.tool_name,
                data=data,
                sanitized_payload=sanitized,
            )
        except ToolChainDepthExceeded as exc:
            response = ToolInvokeResponse(
                success=False,
                tool_name=request.tool_name,
                error=str(exc),
            )
        except Exception as exc:
            response = ToolInvokeResponse(
                success=False,
                tool_name=request.tool_name,
                error=str(exc),
            )
        self.record_tool_invocation(request, response)
        self.record_tool_metric(request.tool_name, response.success)
        return response
