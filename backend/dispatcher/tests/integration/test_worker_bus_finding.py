from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus
from cys_core.infrastructure.bus_transport import DELIVERY_TOPIC, InMemoryBusTransport
from interfaces.worker.orchestrator import WorkerOrchestrator, build_agent_bus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_worker_publishes_signed_bus_envelope():
    registry = SimpleNamespace(
        all=lambda: [
            SimpleNamespace(name="soc", trust_level="internal", bus_recipients=["critic"]),
        ],
        get=lambda name: SimpleNamespace(
            schema_name="SocFinding",
            tools=[],
            skills=[],
            bus_recipients=["critic"],
        ),
    )
    runtime = SimpleNamespace(
        arun=AsyncMock(
            return_value={
                "incident_id": "i1",
                "priority": "high",
                "confidence": 0.8,
                "summary": "ok",
            }
        ),
    )
    transport = InMemoryBusTransport()
    published: list[dict] = []
    transport.subscribe(DELIVERY_TOPIC, lambda msg: published.append(msg))
    orch = WorkerOrchestrator(
        runtime=runtime,
        registry=registry,
        bus=build_agent_bus(registry),
        transport=transport,
    )
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc", payload={"alert": "x"})
    result = await orch.run_job(job)
    assert result.success is True
    assert job.status == WorkerJobStatus.COMPLETED
    assert len(published) == 1
    assert published[0]["type"] == "finding"
    assert published[0]["sender"] == "soc"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_consultant_publishes_to_critic_and_coordinator():
    registry = SimpleNamespace(
        all=lambda: [
            SimpleNamespace(
                name="consultant",
                trust_level="internal",
                bus_recipients=["critic", "coordinator"],
            ),
            SimpleNamespace(name="critic", trust_level="privileged", bus_recipients=[]),
            SimpleNamespace(name="coordinator", trust_level="system", bus_recipients=[]),
        ],
        get=lambda name: SimpleNamespace(
            schema_name="ConsultantFinding",
            tools=[],
            skills=[],
            bus_recipients=["critic", "coordinator"],
        ),
    )
    runtime = SimpleNamespace(
        arun=AsyncMock(
            return_value={
                "topic": "Malware defense",
                "summary": "Use EDR and patching",
                "recommendations": ["Deploy EDR", "Patch monthly"],
                "references": ["CIS 10"],
                "risk_level": "medium",
                "confidence": 0.8,
            }
        ),
    )
    transport = InMemoryBusTransport()
    published: list[dict] = []
    transport.subscribe(DELIVERY_TOPIC, lambda msg: published.append(msg))
    orch = WorkerOrchestrator(
        runtime=runtime,
        registry=registry,
        bus=build_agent_bus(registry),
        transport=transport,
    )
    job = WorkerJob(
        job_id="consultant-j1",
        event_id="e1",
        persona="consultant",
        correlation_id="eng-1",
        payload={"goal": "virus protection"},
    )
    result = await orch.run_job(job)
    assert result.success is True
    recipients = {msg["recipient"] for msg in published}
    # Default GATE_ONLY control-plane mode keeps critic but drops coordinator.
    assert recipients == {"critic"}
