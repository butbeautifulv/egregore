from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# Plain str, not a closed Literal (MSP_BACKLOG.md §8.4 point 1) — the set of valid
# event types is profile-pack-specific (cybersec-soc's "siem.alert"/"edr.alert"/...
# vs. a hypothetical other pack's own vocabulary), not something cys_core/domain
# should hardcode. No exhaustiveness/match code in this codebase branches on these
# specific string values (verified by repo-wide grep) — an unrecognized event_type
# simply matches no RoutingRule, which is the correct fail-open behavior for a
# pack introducing event types core has never heard of. No catalog-driven
# validation is wired in yet (none previously existed to piggyback on — see
# MSP_BACKLOG.md §70's residual-coupling entries for the same honest-deferral
# pattern); this pass only removes the hardcoded closed set from core.
EventType = str

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
    matched_plan_id: str = ""
    matched_rule_idx: int = -1
