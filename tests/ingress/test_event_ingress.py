from __future__ import annotations

import pytest

from cys_core.domain.events.plans import load_plan_routing
from cys_core.domain.events.router import EventRouter
from interfaces.ingress.router import EventIngress


@pytest.mark.unit
def test_event_ingress_routes_siem_alert(tmp_path):
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        """
id: incident-triage
routing:
  rules:
    - event_types: [siem.alert]
      personas: [soc]
""",
        encoding="utf-8",
    )
    router = EventRouter([load_plan_routing(plan)])
    ingress = EventIngress(router=router)
    event, decision, job_ids = ingress.ingest("siem.alert", {"alert": "powershell"}, severity="high")
    assert event.type == "siem.alert"
    assert decision.personas == ["soc"]
    assert len(job_ids) == 1
