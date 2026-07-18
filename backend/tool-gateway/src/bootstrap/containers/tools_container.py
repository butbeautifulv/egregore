from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from bootstrap.container import Container
    from cys_core.domain.tools.models import ToolInvokeCommand

logger = structlog.get_logger(__name__)


def _require_sandbox(sandbox_id: str) -> None:
    # Inlined rather than imported from cys_core.registry.mcp_tools (worker's
    # HTTP client to this gateway, not part of this package) — this package
    # is the gateway server, not a caller of it. See
    # docs/MICROSERVICES_SPLIT_PLAN.md §21.6.
    if not sandbox_id or sandbox_id == "host":
        raise PermissionError("Tool requires sandbox context — denied on host")


def _resolve_scope_violation(command: "ToolInvokeCommand") -> str | None:
    # ScopePolicy has lived in this package's domain layer since the §21.6
    # extraction but was never actually invoked on the tool-invocation path —
    # least-privilege allowlisting only ran in-process, in worker's
    # ScopeMiddleware, which a differently-implemented agent runtime has no
    # obligation to call. Enforcing it here closes that gap at the one
    # chokepoint every runtime's tool calls must cross regardless of
    # implementation. See docs/MICROSERVICES_SPLIT_PLAN.md §22.10/§23.
    from cys_core.domain.security.scope import ScopePolicy
    from cys_core.registry.agents import get_agent_registry

    try:
        definition = get_agent_registry().get(command.persona)
    except KeyError:
        # Fail open on an unknown persona rather than block every tool call
        # for a persona this package's catalog snapshot doesn't have —
        # deliberately conservative rollout stance for a check that has never
        # run here before, not a permanent exception. Logged so a persona
        # that's unexpectedly always missing is visible, not silent.
        logger.warning("tool_gateway_scope_check_unknown_persona", persona=command.persona)
        return None
    return ScopePolicy.from_tools(definition.allowed_tools).check_tool_call(command.tool_name, command.args)


class ToolsContainer:
    """Owns tool-chain policy, invocation use case, and execution gateway."""

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._tool_chain_policy = None
        self._tool_rate_limiter = None
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

    def get_tool_rate_limiter(self):
        # Same RedisRateLimiter class already used for job-queue/follow-up
        # enqueue paths, now also applied per tool call — previously present
        # in this package but only ever wired to those two paths, never to
        # the tool-invocation path itself. docs/MICROSERVICES_SPLIT_PLAN.md
        # §22.10/§23.
        if self._tool_rate_limiter is None:
            from cys_core.security.rate_limit import RedisRateLimiter

            self._tool_rate_limiter = RedisRateLimiter(max_calls=self.settings.max_tool_calls_per_minute)
        return self._tool_rate_limiter

    def _check_rate_limit(self, command: "ToolInvokeCommand") -> None:
        key = f"{command.job_id or command.sandbox_id}:{command.tool_name}"
        self.get_tool_rate_limiter().check(key)

    def _check_scope(self, command: "ToolInvokeCommand") -> None:
        from cys_core.domain.tools.exceptions import ScopeViolation

        mode = self.settings.tool_scope_mode
        if mode == "off":
            return
        violation = _resolve_scope_violation(command)
        if violation is None:
            return
        if mode == "shadow":
            # Rollout found a real gap during implementation (docs/
            # MICROSERVICES_SPLIT_PLAN.md §23): at least one persona's
            # declared tool list didn't match what its own tests exercise it
            # against, which means blind enforcement here would have blocked
            # legitimate calls. Logging every would-be denial so the gap
            # between declared and actually-used tools per persona is visible
            # and fixable before this is ever flipped to "enforce".
            logger.warning(
                "tool_gateway_scope_violation_shadow",
                persona=command.persona,
                tool_name=command.tool_name,
                reason=violation,
            )
            return
        raise ScopeViolation(violation)

    def get_invoke_tool(self):
        if self._invoke_tool is not None:
            return self._invoke_tool
        from cys_core.application.use_cases.invoke_tool import InvokeTool
        from cys_core.infrastructure.tools.adapters import invoke_adapter
        from cys_core.infrastructure.tools.audit import record_tool_invocation
        from cys_core.infrastructure.tools.sanitize import sanitize_tool_output_or_raise
        from cys_core.observability.metrics import metrics

        container = self._container
        self._invoke_tool = InvokeTool(
            require_sandbox=_require_sandbox,
            check_tool_chain=lambda cmd: self.get_tool_chain_policy().check(cmd),
            invoke_adapter=invoke_adapter,
            tool_registry=container.get_tool_registry_port(),
            sanitize_tool_output_or_raise=sanitize_tool_output_or_raise,
            record_tool_invocation=record_tool_invocation,
            record_tool_metric=lambda name, ok: metrics.record_tool_invocation(name, success=ok),
            application_tracing=container.get_application_tracing_port(),
            authz_service=container.get_authz_service(),
            check_scope=self._check_scope,
            check_rate_limit=self._check_rate_limit,
        )
        return self._invoke_tool

    def get_tool_execution_gateway(self):
        if self._tool_execution_gateway is not None:
            return self._tool_execution_gateway
        from cys_core.infrastructure.tools.local_gateway import build_local_tool_execution_gateway

        self._tool_execution_gateway = build_local_tool_execution_gateway(self.get_invoke_tool())
        return self._tool_execution_gateway
