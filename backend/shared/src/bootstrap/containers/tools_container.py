from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bootstrap.container import Container


class ToolsContainer:
    """Owns tool-chain policy, invocation use case, and execution gateway."""

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._tool_chain_policy = None
        self._invoke_tool = None
        self._tool_execution_gateway = None

    @property
    def settings(self):
        return self._container.settings

    def get_tool_chain_policy(self):
        from cys_core.application.tools.tool_chain_policy import ToolChainPolicy

        depth = self.settings.max_high_risk_tool_chain_depth
        policy = self._tool_chain_policy
        if policy is None or policy._max_high_risk_depth != depth:
            self._tool_chain_policy = ToolChainPolicy(max_high_risk_depth=depth)
        return self._tool_chain_policy

    def get_invoke_tool(self):
        if self._invoke_tool is not None:
            return self._invoke_tool
        from cys_core.application.use_cases.invoke_tool import InvokeTool
        from cys_core.infrastructure.tools.adapters import invoke_adapter
        from cys_core.infrastructure.tools.audit import record_tool_invocation
        from cys_core.infrastructure.tools.sanitize import sanitize_tool_output_or_raise
        from cys_core.observability.metrics import metrics
        from cys_core.registry.mcp_tools import require_sandbox

        container = self._container
        self._invoke_tool = InvokeTool(
            require_sandbox=require_sandbox,
            check_tool_chain=lambda cmd: self.get_tool_chain_policy().check(cmd),
            invoke_adapter=invoke_adapter,
            tool_registry=container.get_tool_registry_port(),
            sanitize_tool_output_or_raise=sanitize_tool_output_or_raise,
            record_tool_invocation=record_tool_invocation,
            record_tool_metric=lambda name, ok: metrics.record_tool_invocation(name, success=ok),
            application_tracing=container.get_application_tracing_port(),
            authz_service=container.get_authz_service(),
        )
        return self._invoke_tool

    def get_tool_execution_gateway(self):
        if self._tool_execution_gateway is not None:
            return self._tool_execution_gateway
        from cys_core.infrastructure.tools.local_gateway import build_local_tool_execution_gateway

        self._tool_execution_gateway = build_local_tool_execution_gateway(self.get_invoke_tool())
        return self._tool_execution_gateway
