from __future__ import annotations

from dataclasses import dataclass

from cys_core.domain.policy.pure import classify_tool_risk_pure
from cys_core.domain.reasoning.sgr_models import SgrMode


@dataclass(frozen=True)
class SgrIronPolicyDecision:
    allowed: bool
    reason: str


def check_iron_tool_allowed(
    *,
    tool_name: str,
    allowed_tools: list[str],
    mode: SgrMode,
    profile_id: str,
    policy=None,
) -> SgrIronPolicyDecision:
    if mode != "sgr_iron":
        return SgrIronPolicyDecision(allowed=True, reason="not_iron_mode")
    if tool_name == "reasoning_step":
        return SgrIronPolicyDecision(allowed=True, reason="reasoning_step_always_allowed")
    if tool_name not in allowed_tools:
        return SgrIronPolicyDecision(allowed=False, reason=f"tool_not_in_allowlist:{tool_name}")
    risk = classify_tool_risk_pure(tool_name, policy)
    if risk.value in {"critical", "high"} and tool_name not in {"web_search", "read_document"}:
        return SgrIronPolicyDecision(allowed=False, reason=f"high_risk_blocked_in_iron:{tool_name}")
    return SgrIronPolicyDecision(allowed=True, reason="ok")
