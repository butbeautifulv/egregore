from __future__ import annotations

import pytest

from cys_core.application.use_cases.dispatch_event import apply_conductor_routing
from cys_core.domain.events.models import RoutingDecision, SecurityEvent


@pytest.mark.unit
def test_conductor_routing_disabled(monkeypatch):
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_use_conductor_for_events", False)
    event = SecurityEvent(id="e1", type="siem.alert")
    decision = RoutingDecision(event_id="e1", personas=["soc"], playbook_id="p1")
    out_decision, payload = apply_conductor_routing(event, decision, {"x": 1})
    assert out_decision.personas == ["soc"]
    assert "run_context" in payload


@pytest.mark.unit
def test_conductor_routing_enabled(monkeypatch):
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_use_conductor_for_events", True)
    event = SecurityEvent(id="e1", type="siem.alert")
    decision = RoutingDecision(event_id="e1", personas=["soc", "network"], playbook_id="p1")
    out_decision, payload = apply_conductor_routing(event, decision, {"x": 1})
    assert out_decision.personas == ["conductor"]
    assert payload["suggested_personas"] == ["soc", "network"]
    assert "routing_hints" in payload
