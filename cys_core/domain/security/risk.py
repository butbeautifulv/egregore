from __future__ import annotations

from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.policy.defaults import ACTION_RISK_MAPPING
from cys_core.domain.policy.pure import classify_tool_risk_pure
from cys_core.domain.security.risk_level import RiskLevel

SEVERITY_RISK: dict[str, RiskLevel] = {
    "critical": RiskLevel.CRITICAL,
    "high": RiskLevel.HIGH,
    "medium": RiskLevel.MEDIUM,
    "low": RiskLevel.LOW,
    "info": RiskLevel.LOW,
    "informational": RiskLevel.LOW,
}


def classify_tool_risk(tool_name: str, policy: ProfilePolicyPayload | None = None) -> RiskLevel:
    return classify_tool_risk_pure(tool_name, policy)


def classify_severity(severity: str) -> RiskLevel:
    return SEVERITY_RISK.get(severity.lower().strip(), RiskLevel.MEDIUM)


def parse_threshold(value: str) -> RiskLevel:
    try:
        return RiskLevel(value.lower())
    except ValueError:
        return RiskLevel.LOW


__all__ = ["ACTION_RISK_MAPPING", "RiskLevel", "SEVERITY_RISK", "classify_tool_risk", "classify_severity", "parse_threshold"]
