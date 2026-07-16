from __future__ import annotations

from pydantic import BaseModel, Field

from cys_core.domain.events.models import EventType, RoutingRule, Severity

_SEVERITY_ORDER: list[Severity] = ["info", "low", "medium", "high", "critical"]


class PlanRoutingConfig(BaseModel):
    """Routing section of an agents/plans/*.yaml playbook."""

    id: str
    name: str = ""
    description: str = ""
    rules: list[RoutingRule] = Field(default_factory=list)


def parse_rule(raw: dict) -> RoutingRule:
    event_types = raw.get("event_types") or raw.get("when", {}).get("event_types") or []
    min_severity = raw.get("min_severity") or raw.get("when", {}).get("min_severity")
    personas = raw.get("personas") or raw.get("enqueue") or []
    if isinstance(personas, str):
        personas = [personas]
    return RoutingRule(
        event_types=event_types,
        min_severity=min_severity,
        personas=personas,
        playbook_id=raw.get("playbook_id", ""),
        notify_control=bool(raw.get("notify_control", False)),
    )


# Backward-compatible alias for internal callers
_parse_rule = parse_rule


def parse_plan_routing_from_dict(data: dict, *, plan_id: str = "") -> PlanRoutingConfig:
    rules_raw = data.get("routing", {}).get("rules") or data.get("rules") or []
    rules = [parse_rule(r) for r in rules_raw]
    return PlanRoutingConfig(
        id=data.get("id", plan_id),
        name=data.get("name", ""),
        description=data.get("description", ""),
        rules=rules,
    )


def severity_at_least(actual: Severity, minimum: Severity) -> bool:
    return _SEVERITY_ORDER.index(actual) >= _SEVERITY_ORDER.index(minimum)


def rule_matches(rule: RoutingRule, event_type: EventType, severity: Severity) -> bool:
    if rule.event_types and event_type not in rule.event_types:
        return False
    if rule.min_severity is not None and not severity_at_least(severity, rule.min_severity):
        return False
    return bool(rule.personas)
