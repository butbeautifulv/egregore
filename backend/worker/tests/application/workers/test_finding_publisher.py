from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.application.workers.finding_publisher import WorkerFindingPublisher, should_publish_finding_to_bus
from cys_core.domain.workers.models import WorkerJob


@pytest.mark.unit
def test_should_publish_finding_to_bus() -> None:
    assert should_publish_finding_to_bus(persona="soc", role="worker") is True
    assert should_publish_finding_to_bus(persona="identity", role="worker") is True
    assert should_publish_finding_to_bus(persona="planner", role="control") is False
    assert should_publish_finding_to_bus(persona="critic", role="control") is False
    assert should_publish_finding_to_bus(persona="coordinator", role="control") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finding_publisher_skips_bus_for_planner():
    published: list[dict] = []

    class Bus:
        escalation_paths: set[tuple[str, str]] = set()

        def send_message(self, sender, recipient, msg_type, payload):
            raise AssertionError("planner must not publish findings to bus")

        def receive_message(self, recipient, envelope):
            return None

    transport = SimpleNamespace(publish_delivery=AsyncMock(side_effect=lambda env: published.append(env)))
    publisher = WorkerFindingPublisher(bus=Bus(), transport=transport)
    job = WorkerJob(job_id="planner-fu-1", event_id="e1", persona="planner", correlation_id="inv-1")
    defn = SimpleNamespace(role="control", bus_recipients=[])
    await publisher.publish(
        job=job,
        defn=defn,
        result={"personas": ["identity"], "summary": "plan"},
        sandbox_id="",
        investigation_id="inv-1",
    )
    assert published == []
    transport.publish_delivery.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finding_publisher_publishes_to_bus_and_transport():
    published: list[dict] = []

    class Bus:
        escalation_paths: set[tuple[str, str]] = set()

        def send_message(self, sender, recipient, msg_type, payload):
            return {"signature": "sig-1"}

        def receive_message(self, recipient, envelope):
            return None

    transport = SimpleNamespace(publish_delivery=AsyncMock(side_effect=lambda env: published.append(env)))
    publisher = WorkerFindingPublisher(bus=Bus(), transport=transport)
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc", correlation_id="inv-1")
    defn = SimpleNamespace(bus_recipients=["critic"])
    await publisher.publish(
        job=job,
        defn=defn,
        result={"summary": "ok"},
        sandbox_id="sb-1",
        investigation_id="inv-1",
    )
    assert len(published) == 1
    transport.publish_delivery.assert_awaited()


@pytest.mark.unit
def test_finding_publisher_persists_memory():
    stored: list[dict] = []

    class Writer:
        def append_pending_finding(self, **kwargs):
            stored.append(kwargs)
            return SimpleNamespace(memory_type="pending_finding")

    recorded: list[str] = []
    publisher = WorkerFindingPublisher(
        bus=SimpleNamespace(send_message=lambda *a, **k: {}, receive_message=lambda *a, **k: None),
        transport=SimpleNamespace(publish_delivery=AsyncMock()),
        memory_writer=Writer(),
        record_memory_write=lambda tenant, memory_type: recorded.append(memory_type),
    )
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc", correlation_id="inv-1")
    publisher.persist_memory(job=job, result={"summary": "ok"}, investigation_id="inv-1")
    assert stored
    assert recorded == ["pending_finding"]
