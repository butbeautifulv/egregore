from __future__ import annotations

from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.datasources.authz import AuthorizationDecision, AuthzRequest
from cys_core.domain.datasources.models import DataSource, DataSourceCapability


def effective_capabilities(
    source: DataSource,
    request: AuthzRequest,
    policy: ProfilePolicyPayload | None,
) -> set[DataSourceCapability]:
    caps = set(source.capabilities)
    if policy is None:
        return caps
    grants = policy.datasource_capability_grants.get(request.profile_id, {}).get(source.id, [])
    for grant in grants:
        try:
            caps.add(DataSourceCapability(grant))
        except ValueError:
            continue
    return caps


def check_allowlist_overrides(
    request: AuthzRequest,
    policy: ProfilePolicyPayload | None,
) -> AuthorizationDecision | None:
    """Return deny decision when profile/persona allowlists block access."""
    if policy is None:
        return None
    profile_allow = policy.datasource_allowlist.get(request.profile_id)
    if profile_allow is not None and request.datasource_id not in profile_allow:
        return AuthorizationDecision(
            allowed=False,
            reason="not_in_profile_allowlist",
            matched_rule="profile_datasource_allowlist",
            tags=["deny", "allowlist"],
        )
    persona_map = policy.persona_datasource_allowlist.get(request.profile_id, {})
    persona_allow = persona_map.get(request.persona)
    if persona_allow is not None and request.datasource_id not in persona_allow:
        return AuthorizationDecision(
            allowed=False,
            reason="not_in_persona_allowlist",
            matched_rule="persona_datasource_allowlist",
            tags=["deny", "allowlist"],
        )
    return None
