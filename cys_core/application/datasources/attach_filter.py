from __future__ import annotations

from cys_core.application.datasources.exec_authz import authorize_tool_datasource
from cys_core.application.datasources.tool_bindings import get_tool_datasource_binding, is_get_only_binding
from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID


def filter_attachable_tools(
    tool_names: list[str],
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    persona: str = "",
    tenant_id: str = "default",
) -> list[str]:
    """Drop datasource-backed tools that require non-GET capabilities unless policy grants them."""
    kept: list[str] = []
    for name in tool_names:
        binding = get_tool_datasource_binding(name)
        if binding is None:
            kept.append(name)
            continue
        if is_get_only_binding(binding):
            kept.append(name)
            continue
        decision = authorize_tool_datasource(
            tool_name=name,
            persona=persona or "worker",
            profile_id=profile_id,
            tenant_id=tenant_id,
        )
        if decision is None:
            kept.append(name)
    return kept


def filter_with_policy(
    tool_names: list[str],
    *,
    profile_id: str,
    persona: str,
    policy: ProfilePolicyPayload | None,
) -> list[str]:
    _ = policy
    return filter_attachable_tools(tool_names, profile_id=profile_id, persona=persona)
