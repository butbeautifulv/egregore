from __future__ import annotations

from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.policy.product_payloads import profile_policy_for


def datasource_policy_for(profile_id: str) -> ProfilePolicyPayload:
    """Profile policy slice used for datasource authz overrides."""
    return profile_policy_for(profile_id)
