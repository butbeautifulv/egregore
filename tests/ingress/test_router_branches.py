from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.observability.tracing import get_correlation_id, reset_correlation_id
from interfaces.ingress.router import EventIngress


@pytest.mark.unit
def test_ingest_binds_correlation_id():
    orchestrator = MagicMock()
    orchestrator.enqueue_from_routing_sync.return_value = []
    router = SimpleNamespace(route=lambda event: SimpleNamespace(personas=[], playbook_id=""))
    ingress = EventIngress(router=router, orchestrator=orchestrator)
    ingress.ingest("siem.alert", {}, correlation_id="corr-xyz")
    assert get_correlation_id() == ""
    reset_correlation_id  # no-op if already cleared


@pytest.mark.unit
@pytest.mark.asyncio
async def test_aingest_kafka_fallback_enqueues(monkeypatch):
    orchestrator = MagicMock()
    orchestrator.enqueue_from_routing = AsyncMock(return_value=["soc-e1-x"])
    router = SimpleNamespace(route=lambda event: SimpleNamespace(personas=["soc"], playbook_id="incident-triage"))
    monkeypatch.setattr("interfaces.ingress.router.settings.use_kafka", True)
    monkeypatch.setattr(
        "cys_core.infrastructure.kafka_events.publish_raw_event",
        AsyncMock(return_value=False),
    )
    ingress = EventIngress(router=router, orchestrator=orchestrator)
    event, decision, job_ids = await ingress.aingest("siem.alert", {"a": 1})
    assert job_ids == ["soc-e1-x"]
