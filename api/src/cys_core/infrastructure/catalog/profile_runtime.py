from __future__ import annotations

from dataclasses import dataclass

from cys_core.application.ports.profile_policy import ProfilePolicyPort
from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID


@dataclass(frozen=True)
class ProfileRuntimeView:
    """Thin read-only view over resolved profile policy."""

    profile_id: str
    policy: ProfilePolicyPayload


def get_profile_runtime(
    profile_id: str = DEFAULT_PROFILE_ID,
    *,
    policy_port: ProfilePolicyPort | None = None,
) -> ProfileRuntimeView:
    port = policy_port or _default_policy_port()
    return ProfileRuntimeView(profile_id=profile_id, policy=port.get_policy(profile_id))


def _default_policy_port() -> ProfilePolicyPort:
    from cys_core.infrastructure.catalog.profile_policy import _loader

    return _loader()
