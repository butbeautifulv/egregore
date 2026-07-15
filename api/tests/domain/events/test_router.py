import pytest

from cys_core.domain.events.models import RoutingRule, SecurityEvent
from cys_core.application.plans.plan_loader import load_plan_routing
from cys_core.domain.events.plans import PlanRoutingConfig, rule_matches, severity_at_least
from cys_core.application.routing.event_router import EventRouter
from tests.application.port_fakes import fake_policy_port


def _router(plans):
    return EventRouter(plans, policy_port=fake_policy_port())


@pytest.mark.unit
def test_rule_matches_event_type_and_severity():
    rule = RoutingRule(event_types=["siem.alert"], min_severity="high", personas=["soc"])
    assert rule_matches(rule, "siem.alert", "high")
    assert not rule_matches(rule, "netflow.beacon", "high")
    assert not rule_matches(rule, "siem.alert", "low")


@pytest.mark.unit
def test_severity_at_least():
    assert severity_at_least("critical", "high")
    assert not severity_at_least("low", "high")


@pytest.mark.unit
def test_event_router_routes_siem_to_soc(tmp_path):
    plan_file = tmp_path / "incident.yaml"
    plan_file.write_text(
        """
id: incident-triage
routing:
  rules:
    - event_types: [siem.alert, edr.alert]
      personas: [soc]
      notify_control: true
""",
        encoding="utf-8",
    )
    router = _router([load_plan_routing(plan_file)])
    event = SecurityEvent(id="e1", type="siem.alert", severity="high", payload={"alert": "powershell"})
    decision = router.route(event)
    assert decision.personas == ["soc"]
    assert decision.notify_control is True
    assert decision.playbook_id == "incident-triage"
    assert decision.jobs == ["soc:e1"]


@pytest.mark.unit
def test_event_router_no_match():
    router = _router([])
    event = SecurityEvent(id="e2", type="doc.upload", severity="low")
    decision = router.route(event)
    assert decision.personas == []
    assert decision.reason == "no_matching_rule"


@pytest.mark.unit
def test_event_router_from_plans_dir(tmp_path):
    plan_file = tmp_path / "p.yaml"
    plan_file.write_text(
        """
id: redteam-engagement
routing:
  rules:
    - event_types: [escalation]
      min_severity: high
      personas: [redteam]
      playbook_id: custom-playbook
""",
        encoding="utf-8",
    )
    router = EventRouter.from_plans_dir(tmp_path, policy_port=fake_policy_port())
    decision = router.route(SecurityEvent(id="e3", type="escalation", severity="critical"))
    assert decision.personas == ["redteam"]
    assert decision.playbook_id == "custom-playbook"


@pytest.mark.unit
def test_event_router_skips_non_matching_rules():
    router = _router(
        [
            PlanRoutingConfig(
                id="p1",
                rules=[
                    RoutingRule(event_types=["netflow.beacon"], personas=["network"]),
                    RoutingRule(event_types=["siem.alert"], personas=["soc"]),
                ],
            ),
        ]
    )
    decision = router.route(SecurityEvent(id="e5", type="siem.alert", severity="low"))
    assert decision.personas == ["soc"]


@pytest.mark.unit
def test_event_router_deduplicates_personas():
    router = _router(
        [
            PlanRoutingConfig(
                id="p1",
                rules=[
                    RoutingRule(event_types=["siem.alert"], personas=["soc"]),
                ],
            ),
            PlanRoutingConfig(
                id="p2",
                rules=[
                    RoutingRule(event_types=["siem.alert"], personas=["soc", "network"]),
                ],
            ),
        ]
    )
    decision = router.route(SecurityEvent(id="e4", type="siem.alert", severity="medium"))
    assert decision.personas == ["soc", "network"]
