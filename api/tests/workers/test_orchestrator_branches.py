from __future__ import annotations

import pytest

from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.workers.job_budget import JobBudgetExceeded
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus
from tests.application.workers.factory import FakeAgentRuntime, build_test_orchestrator


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_job_budget_exceeded(monkeypatch):
    orch = build_test_orchestrator(
        runtime=FakeAgentRuntime(side_effect=JobBudgetExceeded("Job tool-call budget exceeded (0 max)")),
    )
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc", payload={})
    result = await orch.run_job(job)
    assert result.success is False
    assert job.status == WorkerJobStatus.FAILED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_security_violation_on_sanitize(monkeypatch):
    class _BlockingSanitizer:
        def sanitize(self, content: str, *, source: str = "user") -> str:
            raise SecurityViolation("blocked")

    orch = build_test_orchestrator(
        runtime=FakeAgentRuntime(return_value={"ok": True}),
        sanitizer=_BlockingSanitizer(),
    )
    job = WorkerJob(job_id="j2", event_id="e1", persona="soc", payload={})
    result = await orch.run_job(job)
    assert result.success is False
    assert job.status == WorkerJobStatus.FAILED
