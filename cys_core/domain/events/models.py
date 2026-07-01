from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "siem.alert",
    "edr.alert",
    "iam.event",
    "netflow.beacon",
    "dns.anomaly",
    "doc.upload",
    "compliance.schedule",
    "finding.reference",
    "escalation",
    "manual.investigation",
    "manual.consultation",
]

Severity = Literal["info", "low", "medium", "high", "critical"]


class SecurityEvent(BaseModel):
    """Structured ingress event for worker routing."""

    id: str
    type: EventType
    source: str = ""
    severity: Severity = "medium"
    payload: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = "default"
    correlation_id: str = ""


class RoutingRule(BaseModel):
    """Deterministic routing rule loaded from plan YAML."""

    event_types: list[EventType] = Field(default_factory=list)
    min_severity: Severity | None = None
    personas: list[str] = Field(default_factory=list)
    playbook_id: str = ""
    notify_control: bool = False


class RoutingDecision(BaseModel):
    """Result of routing one event through the policy engine."""

    event_id: str
    jobs: list[str] = Field(default_factory=list)
    playbook_id: str = ""
    personas: list[str] = Field(default_factory=list)
    notify_control: bool = False
    reason: str = ""
