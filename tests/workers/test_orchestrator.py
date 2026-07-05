from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus
from interfaces.worker.orchestrator import WorkerOrchestrator, build_agent_bus


@pytest.mark.unit
def test_build_agent_bus_registers_workers():
    registry = SimpleNamespace(
        all=lambda: [
            SimpleNamespace(name="soc", trust_level="internal", bus_recipients=["critic"]),
        ]
    )
    bus = build_agent_bus(registry)
    assert "soc" in bus.agent_registry


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_run_job_publishes_finding(monkeypatch):
    registry = SimpleNamespace(
        all=lambda: [
            SimpleNamespace(name="soc", trust_level="internal", bus_recipients=["critic"], schema_name="SocFinding"),
        ],
        get=lambda name: SimpleNamespace(
            schema_name="SocFinding",
            tools=[],
            skills=[],
            bus_recipients=["critic"],
        ),
    )
    runtime = SimpleNamespace(
        arun=AsyncMock(return_value={"incident_id": "i1", "priority": "high", "confidence": 0.8, "summary": "ok"}),
    )
    orch = WorkerOrchestrator(runtime=runtime, registry=registry, bus=build_agent_bus(registry))
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc", payload={"alert": "x"})
    result = await orch.run_job(job)
    assert result.success is True
    assert job.status == WorkerJobStatus.COMPLETED
    assert not orch.sandbox.is_active("j1")


@pytest.mark.unit
def test_enqueue_from_routing_sync():
    from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs
    from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore
    from cys_core.infrastructure.queue import InMemoryJobQueue

    service = EnqueueWorkerJobs(queue=InMemoryJobQueue(), job_store=InMemoryJobStore())
    ids = service.enqueue_from_routing_sync("e1", ["soc"], playbook_id="incident-triage", payload={"a": 1})
    assert len(ids) == 1
    assert ids[0].startswith("soc-e1-")
