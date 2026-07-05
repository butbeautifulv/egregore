from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.workers.job_budget import JobBudgetExceeded
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus
from interfaces.worker.orchestrator import WorkerOrchestrator, build_agent_bus


def _orch_with_mocks(monkeypatch, *, arun_return=None, arun_side_effect=None):
    registry = SimpleNamespace(
        all=lambda: [SimpleNamespace(name="soc", trust_level="internal", bus_recipients=["critic"])],
        get=lambda name: SimpleNamespace(schema_name=None, tools=[], skills=[]),
    )
    runtime = SimpleNamespace(arun=AsyncMock(return_value=arun_return, side_effect=arun_side_effect))
    orch = WorkerOrchestrator(runtime=runtime, registry=registry, bus=build_agent_bus(registry))
    return orch


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_job_budget_exceeded(monkeypatch):
    orch = _orch_with_mocks(
        monkeypatch,
        arun_side_effect=JobBudgetExceeded("Job tool-call budget exceeded (0 max)"),
    )
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc", payload={})
    result = await orch.run_job(job)
    assert result.success is False
    assert job.status == WorkerJobStatus.FAILED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_security_violation_on_sanitize(monkeypatch):
    def raise_violation(text, source="external"):
        raise SecurityViolation("blocked")

    registry = SimpleNamespace(
        all=lambda: [SimpleNamespace(name="soc", trust_level="internal", bus_recipients=["critic"])],
        get=lambda name: SimpleNamespace(schema_name=None, tools=[], skills=[]),
    )
    runtime = SimpleNamespace(arun=AsyncMock(return_value={"ok": True}))
    orch = WorkerOrchestrator(
        runtime=runtime,
        registry=registry,
        bus=build_agent_bus(registry),
        sanitizer=SimpleNamespace(sanitize=raise_violation),
    )
    job = WorkerJob(job_id="j2", event_id="e1", persona="soc", payload={})
    result = await orch.run_job(job)
    assert result.success is False
    assert job.status == WorkerJobStatus.FAILED
