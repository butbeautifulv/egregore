from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from interfaces.ingress.router import EventIngress


@pytest.mark.integration
def test_ingest_enqueues_worker_jobs():
    orchestrator = MagicMock()
    orchestrator.enqueue_from_routing_sync.return_value = ["soc-e1-abc"]
    router = SimpleNamespace(
        route=lambda event: SimpleNamespace(personas=["soc"], playbook_id="incident-triage", notify_control=False)
    )
    ingress = EventIngress(router=router, orchestrator=orchestrator)
    event, decision, job_ids = ingress.ingest("siem.alert", {"alert": "test"}, severity="high")
    assert event.type == "siem.alert"
    assert decision.personas == ["soc"]
    assert job_ids == ["soc-e1-abc"]
    orchestrator.enqueue_from_routing_sync.assert_called_once()
