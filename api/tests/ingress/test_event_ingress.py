from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.plans.plan_loader import load_plan_routing
from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs
from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.infrastructure.queue import InMemoryJobQueue
from interfaces.ingress.router import EventIngress
from tests.application.port_fakes import fake_correlation_id_port
from tests.conftest import make_event_router


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
    router = make_event_router([load_plan_routing(plan)])
    enqueuer = EnqueueWorkerJobs(queue=InMemoryJobQueue(), job_store=MagicMock())
    route_and_enqueue = RouteAndEnqueueEvent(
        router=router,
        enqueuer=enqueuer,
        correlation_id_port=fake_correlation_id_port(),
    )
    ingress = EventIngress(route_and_enqueue=route_and_enqueue)
    event, decision, job_ids = ingress.ingest("siem.alert", {"alert": "powershell"}, severity="high")
    assert event.type == "siem.alert"
    assert decision.personas == ["soc"]
    assert len(job_ids) == 1
