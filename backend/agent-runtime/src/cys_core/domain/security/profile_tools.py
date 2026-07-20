from __future__ import annotations

from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.policy.defaults import PROFILE_TOOL_ALLOWLIST
from cys_core.domain.policy.pure import allowlist_for_profile, filter_tools_pure


def filter_tools_for_profile(
    tool_names: list[str],
    profile_id: str,
    *,
    policy: ProfilePolicyPayload | None = None,
) -> list[str]:
    return filter_tools_pure(tool_names, profile_id, policy=policy)


__all__ = ["PROFILE_TOOL_ALLOWLIST", "filter_tools_for_profile", "allowlist_for_profile"]
