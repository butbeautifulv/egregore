from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __le__(self, other: "RiskLevel") -> bool:
        order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        return order.index(self) <= order.index(other)


ACTION_RISK_MAPPING: dict[str, RiskLevel] = {
    "parse_netflow": RiskLevel.LOW,
    "enrich_ioc": RiskLevel.LOW,
    "correlate_dns": RiskLevel.LOW,
    "dedup_alerts": RiskLevel.LOW,
    "build_timeline": RiskLevel.LOW,
    "correlate_findings": RiskLevel.LOW,
    "check_control": RiskLevel.LOW,
    "map_framework": RiskLevel.LOW,
    "audit_evidence": RiskLevel.LOW,
    "read_repo_metadata": RiskLevel.LOW,
    "parse_sast_report": RiskLevel.LOW,
    "analyze_workflow": RiskLevel.MEDIUM,
    "write_file": RiskLevel.MEDIUM,
    "run_active_scan": RiskLevel.HIGH,
    "execute_command": RiskLevel.CRITICAL,
    "send_email": RiskLevel.HIGH,
    "database_delete": RiskLevel.CRITICAL,
    "transfer_funds": RiskLevel.CRITICAL,
}

SEVERITY_RISK: dict[str, RiskLevel] = {
    "critical": RiskLevel.CRITICAL,
    "high": RiskLevel.HIGH,
    "medium": RiskLevel.MEDIUM,
    "low": RiskLevel.LOW,
    "info": RiskLevel.LOW,
    "informational": RiskLevel.LOW,
}


def classify_tool_risk(tool_name: str) -> RiskLevel:
    return ACTION_RISK_MAPPING.get(tool_name, RiskLevel.HIGH)


def classify_severity(severity: str) -> RiskLevel:
    return SEVERITY_RISK.get(severity.lower().strip(), RiskLevel.MEDIUM)


def parse_threshold(value: str) -> RiskLevel:
    try:
        return RiskLevel(value.lower())
    except ValueError:
        return RiskLevel.LOW
