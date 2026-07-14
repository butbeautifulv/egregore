from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.application.port_fakes import fake_correlation_id_port
from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.domain.events.models import RoutingDecision
from cys_core.observability.tracing import get_correlation_id, reset_correlation_id
from interfaces.ingress.router import EventIngress


def _ingress(router: SimpleNamespace, orchestration: MagicMock, *, use_kafka: bool = False) -> EventIngress:
    route_and_enqueue = RouteAndEnqueueEvent(
        router=router,
        enqueuer=orchestration,
        correlation_id_port=fake_correlation_id_port(),
        use_kafka=use_kafka,
        publish_raw_event=AsyncMock(return_value=False),
    )
    return EventIngress(route_and_enqueue=route_and_enqueue)


@pytest.mark.unit
def test_ingest_binds_correlation_id():
    orchestration = MagicMock()
    orchestration.enqueue_from_routing_sync.return_value = []
    router = SimpleNamespace(
        route=lambda event, **_: RoutingDecision(event_id=event.id, personas=[], playbook_id="")
    )
    ingress = _ingress(router, orchestration)
    ingress.ingest("siem.alert", {}, correlation_id="corr-xyz")
    assert get_correlation_id() == ""
    reset_correlation_id  # no-op if already cleared


@pytest.mark.unit
@pytest.mark.asyncio
async def test_aingest_kafka_fallback_enqueues(monkeypatch):
    orchestration = MagicMock()
    orchestration.enqueue_from_routing = AsyncMock(return_value=["soc-e1-x"])
    router = SimpleNamespace(
        route=lambda event, **_: RoutingDecision(event_id=event.id, personas=["soc"], playbook_id="incident-triage")
    )
    monkeypatch.setattr(
        "cys_core.infrastructure.kafka_events.publish_raw_event",
        AsyncMock(return_value=False),
    )
    ingress = _ingress(router, orchestration, use_kafka=True)
    event, decision, job_ids = await ingress.aingest("siem.alert", {"a": 1})
    assert job_ids == ["soc-e1-x"]
