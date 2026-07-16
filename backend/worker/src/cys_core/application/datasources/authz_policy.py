from __future__ import annotations

from cys_core.application.datasources.authz_overrides import check_allowlist_overrides, effective_capabilities
from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.datasources.authz import AuthorizationDecision, AuthzRequest
from cys_core.domain.datasources.models import DataSource, DataSourceCapability
from cys_core.domain.datasources.validation import classification_allows
from cys_core.domain.security.classification import persona_clearance_for

TRUST_TO_ROLES: dict[str, list[str]] = {
    "untrusted": ["guest"],
    "internal": ["reader", "worker"],
    "privileged": ["operator", "worker"],
    "system": ["admin", "operator"],
}


def persona_roles(persona: str, *, trust_level: str = "internal") -> list[str]:
    roles = list(TRUST_TO_ROLES.get(trust_level, ["reader"]))
    if persona in {"coordinator", "critic"}:
        roles.append("control")
    return sorted(set(roles))


def authorize_datasource_access(
    request: AuthzRequest,
    source: DataSource,
    *,
    trust_level: str = "internal",
    policy: ProfilePolicyPayload | None = None,
) -> AuthorizationDecision:
    allowlist_deny = check_allowlist_overrides(request, policy)
    if allowlist_deny is not None:
        return allowlist_deny
    caps = effective_capabilities(source, request, policy)
    if request.capability in {DataSourceCapability.QUERY, DataSourceCapability.MUTATE}:
        if request.capability not in caps:
            return AuthorizationDecision(
                allowed=False,
                reason="capability_not_granted",
                matched_rule="get_only_default",
                tags=["deny", "capability"],
            )
    if source.allowed_roles:
        roles = set(persona_roles(request.persona, trust_level=trust_level))
        if not roles.intersection(source.allowed_roles):
            return AuthorizationDecision(
                allowed=False,
                reason="role_not_allowed",
                matched_rule="allowed_roles",
                tags=["deny", "rbac"],
            )
    clearance = persona_clearance_for(request.persona)
    if not classification_allows(clearance, source.classification):
        return AuthorizationDecision(
            allowed=False,
            reason="classification_denied",
            matched_rule="classification_check",
            tags=["deny", "abac"],
        )
    return AuthorizationDecision(
        allowed=True,
        reason="allowed",
        matched_rule="default_allow",
        tags=["allow"],
    )
