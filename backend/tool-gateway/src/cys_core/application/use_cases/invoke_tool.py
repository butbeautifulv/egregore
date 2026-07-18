from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cys_core.application.authz.service import AuthzDenied
from cys_core.application.datasources.args_validation import build_schema_mismatch_payload, validate_tool_args
from cys_core.application.datasources.deny_errors import build_deny_payload
from cys_core.application.datasources.exec_authz import authorize_tool_datasource
from cys_core.application.datasources.schema_fetch import fetch_tool_input_schema
from cys_core.application.datasources.tool_bindings import get_tool_datasource_binding
from cys_core.application.datasources.trace_audit import record_datasource_authz_audit, record_schema_mismatch_audit
from cys_core.application.ports.tool_registry import ToolRegistryPort
from cys_core.application.ports.tracing_ports import NOOP_APPLICATION_TRACING, ApplicationTracingPort
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.datasources.authz import AuthorizationDecision
from cys_core.domain.datasources.schema_models import ModelFamily
from cys_core.domain.tools.exceptions import SandboxTokenInvalid, ScopeViolation, ToolChainDepthExceeded
from cys_core.domain.tools.models import ToolInvokeCommand, ToolInvokeResult
from cys_core.security.rate_limit import RateLimitExceeded


class InvokeTool:
    """Authorize, execute tool backend, sanitize response, audit."""

    def __init__(
        self,
        *,
        require_sandbox: Callable[[str], None],
        check_tool_chain: Callable[[ToolInvokeCommand], None],
        invoke_adapter: Callable[[str, dict[str, Any]], dict[str, Any] | None],
        tool_registry: ToolRegistryPort,
        sanitize_tool_output_or_raise: Callable[[Any], str],
        record_tool_invocation: Callable[[ToolInvokeCommand, ToolInvokeResult], None],
        record_tool_metric: Callable[[str, bool], None] | None = None,
        application_tracing: ApplicationTracingPort | None = None,
        authz_service: Any | None = None,
        check_scope: Callable[[ToolInvokeCommand], None] | None = None,
        check_rate_limit: Callable[[ToolInvokeCommand], None] | None = None,
        check_sandbox_token: Callable[[ToolInvokeCommand], None] | None = None,
    ) -> None:
        self.require_sandbox = require_sandbox
        self.check_tool_chain = check_tool_chain
        self.invoke_adapter = invoke_adapter
        self.tool_registry = tool_registry
        self.sanitize_tool_output_or_raise = sanitize_tool_output_or_raise
        self.record_tool_invocation = record_tool_invocation
        self.record_tool_metric = record_tool_metric or (lambda _name, _ok: None)
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING
        self._authz_service = authz_service
        # Defaults are no-ops rather than required args so every existing caller/test
        # that predates this check keeps working unchanged — the Tool Gateway container
        # (bootstrap/containers/tools_container.py) wires the real enforcement in.
        # docs/MICROSERVICES_SPLIT_PLAN.md §22.10/§23: these two close the gap where
        # ScopePolicy/RedisRateLimiter existed in this package's domain layer but were
        # never actually invoked on the tool-invocation path.
        self.check_scope = check_scope or (lambda _cmd: None)
        self.check_rate_limit = check_rate_limit or (lambda _cmd: None)
        # docs/MICROSERVICES_SPLIT_PLAN.md §11.5/§37: mint_sandbox_token() has minted a
        # signed, time-bound token identifying which sandboxed run is calling since it was
        # first built, but nothing ever verified it here — the one place every tool call
        # actually crosses the trust boundary. Same no-op-default rollout shape as
        # check_scope/check_rate_limit above.
        self.check_sandbox_token = check_sandbox_token or (lambda _cmd: None)

    def _datasource_deny_response(
        self,
        command: ToolInvokeCommand,
        decision: AuthorizationDecision,
    ) -> ToolInvokeResult:
        binding = get_tool_datasource_binding(command.tool_name)
        assert binding is not None
        profile_id = command.profile_id or DEFAULT_PROFILE_ID
        deny = build_deny_payload(decision=decision, binding=binding, profile_id=profile_id)
        record_datasource_authz_audit(
            decision=decision,
            binding=binding,
            profile_id=profile_id,
            persona=command.persona,
        )
        return ToolInvokeResult(
            success=False,
            tool_name=command.tool_name,
            error=decision.reason,
            data={"deny": deny.model_dump()},
        )

    def _schema_mismatch_response(self, command: ToolInvokeCommand, errors: list[str]) -> ToolInvokeResult:
        profile_id = command.profile_id or DEFAULT_PROFILE_ID
        mismatch = build_schema_mismatch_payload(command.tool_name, errors)
        record_schema_mismatch_audit(
            tool_name=command.tool_name,
            profile_id=profile_id,
            persona=command.persona,
            errors=errors,
        )
        return ToolInvokeResult(
            success=False,
            tool_name=command.tool_name,
            error="schema_mismatch",
            data={"schema_mismatch": mismatch.model_dump()},
        )

    def _validate_args(self, command: ToolInvokeCommand) -> ToolInvokeResult | None:
        schema = fetch_tool_input_schema(command.tool_name, self.tool_registry, family=ModelFamily.OPENAI)
        if schema is None:
            return None
        errors = validate_tool_args(command.args, schema, family=ModelFamily.OPENAI)
        if errors:
            return self._schema_mismatch_response(command, errors)
        return None

    def _datasource_subject(self, command: ToolInvokeCommand) -> str:
        if command.workspace_id:
            return f"workspace:{command.workspace_id}"
        if command.user_id:
            return f"user:{command.user_id}"
        if command.organization_id:
            return f"organization:{command.organization_id}#member"
        return ""

    def _rebac_deny_response(self, command: ToolInvokeCommand) -> ToolInvokeResult | None:
        if self._authz_service is None or getattr(self._authz_service, "mode", "off") == "off":
            return None
        binding = get_tool_datasource_binding(command.tool_name)
        if binding is None:
            return None
        subject = self._datasource_subject(command)
        if not subject:
            return None
        try:
            self._authz_service.check(
                subject,
                "can_query",
                f"datasource:{binding.datasource_id}",
            )
        except AuthzDenied:
            return ToolInvokeResult(
                success=False,
                tool_name=command.tool_name,
                error="AUTHZ_DENIED",
                data={
                    "deny": {
                        "code": "AUTHZ_DENIED",
                        "datasource_id": binding.datasource_id,
                        "relation": "can_query",
                    }
                },
            )
        return None

    def _execute_tool(self, command: ToolInvokeCommand) -> dict[str, Any]:
        adapter_result = self.invoke_adapter(command.tool_name, command.args)
        if adapter_result is not None:
            return adapter_result
        # No fallback to tool_registry.get(...).invoke(...) here by design: every
        # tool meant to be reachable through the Tool Gateway (external I/O —
        # SIEM/RAG/web/files/sandbox/veil/nessus) has a plain-function adapter
        # registered above. Tools with no adapter are agent-runtime-internal
        # primitives (reasoning/orchestration/LLM calls) that only make sense
        # inside the in-process LangGraph loop and were never meant to cross
        # this HTTP boundary — see docs/MICROSERVICES_SPLIT_PLAN.md §21.5.
        raise KeyError(
            f"tool {command.tool_name!r} has no Tool Gateway adapter — either unregistered, "
            "or an agent-runtime-internal tool not routable through the gateway"
        )

    def execute(self, command: ToolInvokeCommand) -> ToolInvokeResult:
        profile_id = command.profile_id or DEFAULT_PROFILE_ID
        with self._tracing.span(
            "tool.invoke",
            tool_name=command.tool_name,
            persona=command.persona,
            job_id=command.job_id,
            engagement_id=command.correlation_id,
        ):
            return self._execute_inner(command, profile_id)

    def _execute_inner(self, command: ToolInvokeCommand, profile_id: str) -> ToolInvokeResult:
        try:
            self.require_sandbox(command.sandbox_id)
            self.check_tool_chain(command)
            self.check_sandbox_token(command)
            self.check_scope(command)
            self.check_rate_limit(command)
            deny = authorize_tool_datasource(
                tool_name=command.tool_name,
                persona=command.persona,
                profile_id=profile_id,
            )
            if deny is not None:
                response = self._datasource_deny_response(command, deny)
                self.record_tool_invocation(command, response)
                self.record_tool_metric(command.tool_name, False)
                return response
            rebac_deny = self._rebac_deny_response(command)
            if rebac_deny is not None:
                self.record_tool_invocation(command, rebac_deny)
                self.record_tool_metric(command.tool_name, False)
                return rebac_deny
            schema_deny = self._validate_args(command)
            if schema_deny is not None:
                self.record_tool_invocation(command, schema_deny)
                self.record_tool_metric(command.tool_name, False)
                return schema_deny
            binding = get_tool_datasource_binding(command.tool_name)
            if binding is not None:
                record_datasource_authz_audit(
                    decision=AuthorizationDecision(
                        allowed=True,
                        reason="allowed",
                        matched_rule="default_allow",
                        tags=["allow"],
                    ),
                    binding=binding,
                    profile_id=profile_id,
                    persona=command.persona,
                )
            data = self._execute_tool(command)
            sanitized = self.sanitize_tool_output_or_raise(data)
            response = ToolInvokeResult(
                success=True,
                tool_name=command.tool_name,
                data=data,
                sanitized_payload=sanitized,
            )
        except ToolChainDepthExceeded as exc:
            response = ToolInvokeResult(
                success=False,
                tool_name=command.tool_name,
                error=str(exc),
            )
        except ScopeViolation as exc:
            response = ToolInvokeResult(
                success=False,
                tool_name=command.tool_name,
                error=str(exc),
            )
        except SandboxTokenInvalid as exc:
            response = ToolInvokeResult(
                success=False,
                tool_name=command.tool_name,
                error=str(exc),
            )
        except RateLimitExceeded as exc:
            response = ToolInvokeResult(
                success=False,
                tool_name=command.tool_name,
                error=str(exc),
            )
        except Exception as exc:
            response = ToolInvokeResult(
                success=False,
                tool_name=command.tool_name,
                error=str(exc),
            )
        self.record_tool_invocation(command, response)
        self.record_tool_metric(command.tool_name, response.success)
        return response
