from __future__ import annotations

from cys_core.domain.policy.pure import classify_tool_risk_pure, filter_tools_pure
from cys_core.domain.security.risk_level import RiskLevel


def classify_tool_risk_for_profile(tool_name: str, profile_id: str) -> RiskLevel:
    from cys_core.infrastructure.catalog.profile_policy import get_profile_policy

    try:
        return classify_tool_risk_pure(tool_name, get_profile_policy(profile_id))
    except Exception:
        return classify_tool_risk_pure(tool_name, None)


def filter_tools_for_profile_live(tool_names: list[str], profile_id: str) -> list[str]:
    from cys_core.infrastructure.catalog.profile_policy import get_profile_policy

    try:
        policy = get_profile_policy(profile_id)
    except Exception:
        policy = None
    return filter_tools_pure(tool_names, profile_id, policy=policy)
