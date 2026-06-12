from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.domain.events.models import RoutingDecision


@pytest.mark.unit
def test_route_and_enqueue_sync():
    router = SimpleNamespace(
        route=lambda event: RoutingDecision(
            event_id=event.id,
            personas=["soc"],
            playbook_id="triage",
            reason="match",
        ),
    )
    enqueuer = MagicMock()
    enqueuer.enqueue_from_routing_sync.return_value = ["soc-evt-1"]
    use_case = RouteAndEnqueueEvent(router=router, enqueuer=enqueuer, use_kafka=False)
    event, decision, job_ids = use_case.execute("siem.alert", {"x": 1})
    assert event.type == "siem.alert"
    assert decision.personas == ["soc"]
    assert job_ids == ["soc-evt-1"]
