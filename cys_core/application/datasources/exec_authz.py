from __future__ import annotations

from cys_core.application.datasources.authz_policy import authorize_datasource_access
from cys_core.application.datasources.policy_resolver import datasource_policy_for
from cys_core.application.datasources.providers import get_datasource_catalog_port
from cys_core.application.datasources.tool_bindings import get_tool_datasource_binding
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.datasources.authz import AuthorizationDecision, AuthzRequest
from cys_core.domain.datasources.models import DataSource, DataSourceCapability


def _resolve_source(binding_datasource_id: str) -> DataSource:
    try:
        catalog = get_datasource_catalog_port()
        source = catalog.get(binding_datasource_id)
        if source is not None:
            return source
    except RuntimeError:
        pass
    return DataSource(
        id=binding_datasource_id,
        type=binding_datasource_id,
        capabilities=[DataSourceCapability.GET, DataSourceCapability.LIST],
    )


def authorize_tool_datasource(
    *,
    tool_name: str,
    persona: str,
    profile_id: str | None = None,
    tenant_id: str = "default",
) -> AuthorizationDecision | None:
    """Return deny decision for datasource-backed tools; None when not applicable or allowed."""
    binding = get_tool_datasource_binding(tool_name)
    if binding is None:
        return None
    pid = profile_id or DEFAULT_PROFILE_ID
    policy = datasource_policy_for(pid)
    source = _resolve_source(binding.datasource_id)
    decision = authorize_datasource_access(
        AuthzRequest(
            persona=persona,
            profile_id=pid,
            tenant_id=tenant_id,
            datasource_id=binding.datasource_id,
            capability=binding.capability,
            tool_name=tool_name,
        ),
        source,
        policy=policy,
    )
    return None if decision.allowed else decision
