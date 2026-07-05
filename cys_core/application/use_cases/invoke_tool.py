from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from cys_core.application.datasources.args_validation import build_schema_mismatch_payload, validate_tool_args
from cys_core.application.datasources.deny_errors import build_deny_payload
from cys_core.application.datasources.exec_authz import authorize_tool_datasource
from cys_core.application.datasources.schema_fetch import fetch_tool_input_schema
from cys_core.application.datasources.tool_bindings import get_tool_datasource_binding
from cys_core.application.datasources.trace_audit import record_datasource_authz_audit, record_schema_mismatch_audit
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.datasources.authz import AuthorizationDecision
from cys_core.domain.datasources.schema_models import ModelFamily
from cys_core.domain.tools.exceptions import ToolChainDepthExceeded
from cys_core.domain.tools.models import ToolInvokeCommand, ToolInvokeResult


from cys_core.application.ports.tool_registry import ToolRegistryPort
from cys_core.application.ports.tracing_ports import ApplicationTracingPort, NOOP_APPLICATION_TRACING
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
        check_tool_chain: Callable[[ToolInvokeCommand], None],
        invoke_adapter: Callable[[str, dict[str, Any]], dict[str, Any] | None],
        tool_registry: ToolRegistryPort,
        sanitize_tool_output_or_raise: Callable[[Any], str],
        record_tool_invocation: Callable[[ToolInvokeCommand, ToolInvokeResult], None],
        record_tool_metric: Callable[[str, bool], None] | None = None,
        application_tracing: ApplicationTracingPort | None = None,
    ) -> None:
        self.require_sandbox = require_sandbox
        self.check_tool_chain = check_tool_chain
        self.invoke_adapter = invoke_adapter
        self.tool_registry = tool_registry
        self.sanitize_tool_output_or_raise = sanitize_tool_output_or_raise
        self.record_tool_invocation = record_tool_invocation
        self.record_tool_metric = record_tool_metric or (lambda _name, _ok: None)
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING

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

    def _execute_tool(self, command: ToolInvokeCommand) -> dict[str, Any]:
        adapter_result = self.invoke_adapter(command.tool_name, command.args)
        if adapter_result is not None:
            return adapter_result
        base = self.tool_registry.get(command.tool_name)
        raw = base.invoke(command.args)
        return _normalize_raw_result(raw)

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
            schema_deny = self._validate_args(command)
            if schema_deny is not None:
                self.record_tool_invocation(command, schema_deny)
                self.record_tool_metric(command.tool_name, False)
                return schema_deny
            binding = get_tool_datasource_binding(command.tool_name)
            if binding is not None:
                record_datasource_authz_audit(
                    decision=AuthorizationDecision(allowed=True, reason="allowed", matched_rule="default_allow", tags=["allow"]),
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
        except Exception as exc:
            response = ToolInvokeResult(
                success=False,
                tool_name=command.tool_name,
                error=str(exc),
            )
        self.record_tool_invocation(command, response)
        self.record_tool_metric(command.tool_name, response.success)
        return response
