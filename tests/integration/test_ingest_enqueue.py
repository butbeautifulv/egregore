from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.application.port_fakes import fake_correlation_id_port
from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from interfaces.ingress.router import EventIngress


@pytest.mark.integration
def test_ingest_enqueues_worker_jobs():
    orchestration = MagicMock()
    orchestration.enqueue_from_routing_sync.return_value = ["soc-e1-abc"]

    router = SimpleNamespace(
        route=lambda event: SimpleNamespace(personas=["soc"], playbook_id="incident-triage", notify_control=False)
    )
    route_and_enqueue = RouteAndEnqueueEvent(
        router=router,
        enqueuer=orchestration,
        correlation_id_port=fake_correlation_id_port(),
    )
    ingress = EventIngress(route_and_enqueue=route_and_enqueue)
    event, decision, job_ids = ingress.ingest("siem.alert", {"alert": "test"}, severity="high")
    assert event.type == "siem.alert"
    assert decision.personas == ["soc"]
    assert job_ids == ["soc-e1-abc"]
    orchestration.enqueue_from_routing_sync.assert_called_once()
