from __future__ import annotations

from cys_core.domain.datasources.authz import AuthorizationDecision
from cys_core.domain.datasources.tool_metadata import ToolDataSourceBinding
from cys_core.domain.runs.trace_models import ToolCallTraceFields, policy_trace, tool_call_trace
from cys_core.domain.runs.trajectory import TraceEvent
from cys_core.application.datasources.providers import get_datasource_audit_port


def policy_event_from_decision(
    *,
    decision: AuthorizationDecision,
    profile_id: str,
    datasource_id: str,
) -> TraceEvent:
    return policy_trace(
        "datasource_authz",
        rule=decision.matched_rule or decision.reason,
        decision="allow" if decision.allowed else "deny",
        profile_id=profile_id,
    )


def tool_attempt_event(
    *,
    binding: ToolDataSourceBinding,
    success: bool,
) -> TraceEvent:
    return tool_call_trace(
        binding.tool_name,
        ToolCallTraceFields(
            tool=binding.tool_name,
            args_digest=binding.datasource_id,
            success=success,
        ),
    )


def record_datasource_authz_audit(
    *,
    decision: AuthorizationDecision,
    binding: ToolDataSourceBinding,
    profile_id: str,
    persona: str,
) -> None:
    policy_evt = policy_event_from_decision(
        decision=decision,
        profile_id=profile_id,
        datasource_id=binding.datasource_id,
    )
    tool_evt = tool_attempt_event(binding=binding, success=decision.allowed)
    get_datasource_audit_port().append(
        {
            "kind": "policy",
            "persona": persona,
            "profile_id": profile_id,
            "datasource_id": binding.datasource_id,
            "capability": binding.capability.value,
            "tool_name": binding.tool_name,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "matched_rule": decision.matched_rule,
            "tags": decision.tags,
            "policy_event": policy_evt.model_dump(mode="json"),
            "tool_event": tool_evt.model_dump(mode="json"),
        }
    )


def record_schema_mismatch_audit(
    *,
    tool_name: str,
    profile_id: str,
    persona: str,
    errors: list[str],
) -> None:
    policy_evt = policy_trace(
        "schema_validation",
        rule="args_schema",
        decision="deny",
        profile_id=profile_id,
    )
    tool_evt = tool_call_trace(
        tool_name,
        ToolCallTraceFields(tool=tool_name, args_digest="schema_mismatch", success=False),
    )
    get_datasource_audit_port().append(
        {
            "kind": "schema_mismatch",
            "persona": persona,
            "profile_id": profile_id,
            "tool_name": tool_name,
            "allowed": False,
            "reason": "schema_mismatch",
            "errors": errors,
            "policy_event": policy_evt.model_dump(mode="json"),
            "tool_event": tool_evt.model_dump(mode="json"),
        }
    )
