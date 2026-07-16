from __future__ import annotations

from cys_core.domain.datasources.authz import AuthorizationDecision
from cys_core.domain.datasources.tool_metadata import DataSourceDenyPayload, ToolDataSourceBinding


def build_deny_payload(
    *,
    decision: AuthorizationDecision,
    binding: ToolDataSourceBinding,
    profile_id: str,
) -> DataSourceDenyPayload:
    return DataSourceDenyPayload(
        reason=decision.reason,
        matched_rule=decision.matched_rule,
        tags=list(decision.tags),
        datasource_id=binding.datasource_id,
        capability=binding.capability.value,
        tool_name=binding.tool_name,
        profile_id=profile_id,
    )
