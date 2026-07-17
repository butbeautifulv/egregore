from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyGateDecision:
    allowed: bool
    reason: str


def check_policy_fail_closed(*, policy_loaded: bool, tool_name: str) -> PolicyGateDecision:
    if not policy_loaded:
        return PolicyGateDecision(allowed=False, reason="policy_missing_fail_closed")
    if not tool_name.strip():
        return PolicyGateDecision(allowed=False, reason="empty_tool")
    return PolicyGateDecision(allowed=True, reason="ok")
