from __future__ import annotations

import pytest

from cys_core.domain.events.plans import parse_plan_routing_from_dict, rule_matches, severity_at_least


@pytest.mark.unit
def test_parse_plan_routing_from_dict_enqueue_alias() -> None:
    plan = parse_plan_routing_from_dict(
        {
            "id": "triage",
            "routing": {
                "rules": [
                    {
                        "event_types": ["siem.alert"],
                        "enqueue": "soc",
                        "min_severity": "medium",
                    }
                ]
            },
        },
        plan_id="fallback-id",
    )
    assert plan.id == "triage"
    assert plan.rules[0].personas == ["soc"]


@pytest.mark.unit
def test_rule_matches_and_severity() -> None:
    plan = parse_plan_routing_from_dict(
        {"rules": [{"event_types": ["siem.alert"], "personas": ["soc"], "min_severity": "high"}]}
    )
    rule = plan.rules[0]
    assert rule_matches(rule, "siem.alert", "high")
    assert not rule_matches(rule, "siem.alert", "medium")
    assert severity_at_least("critical", "high")
