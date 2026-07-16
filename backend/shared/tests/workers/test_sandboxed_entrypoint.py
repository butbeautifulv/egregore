from __future__ import annotations

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest

from cys_core.domain.workers.job_budget import JobBudgetTracker
from cys_core.domain.workers.models import RunResult, WorkerJob
from cys_core.infrastructure.execution.envelope import SubprocessJobEnvelope
from cys_core.infrastructure.execution.sandboxed_entrypoint import execute_sandboxed_job


class FakeMetrics:
    def __init__(self) -> None:
        self.timeouts: list[str] = []
        self.usage: list[tuple[str, int, float]] = []

    @contextmanager
    def track_worker_job(self, persona: str):
        state = {"status": "success"}
        yield state

    def record_worker_job_timeout(self, persona: str) -> None:
        self.timeouts.append(persona)

    def record_job_usage(self, persona: str, *, tokens: int, cost_usd: float) -> None:
        self.usage.append((persona, tokens, cost_usd))


class FakeToolChainPolicy:
    def __init__(self) -> None:
        self.cleared: list[str] = []

    def clear(self, job_id: str) -> None:
        self.cleared.append(job_id)


class FakeRunWorkerJob:
    def __init__(
        self,
        *,
        sleep_s: float = 0.0,
        salvage_result: RunResult | None = None,
        checks_budget_configured: bool = False,
    ) -> None:
        self.sleep_s = sleep_s
        self.salvage_result = salvage_result
        self.checks_budget_configured = checks_budget_configured
        self.budget_was_configured_during_execute: bool | None = None
        self.mark_job_timeout = AsyncMock()

    async def execute(self, job: WorkerJob, budgeted: WorkerJob, session_id: str, job_state: dict) -> RunResult:
        if self.checks_budget_configured:
            self.budget_was_configured_during_execute = JobBudgetTracker.get(session_id) is not None
        if self.sleep_s:
            await asyncio.sleep(self.sleep_s)
        return RunResult(job_id=job.job_id, persona=job.persona, success=True)

    async def try_salvage_partial(self, job, session_id, job_state, *, reason="worker_job_timeout"):
        return self.salvage_result


def _envelope(job_id: str = "j1") -> SubprocessJobEnvelope:
    job = WorkerJob(job_id=job_id, event_id="e1", persona="soc", payload={"alert": "x"})
    return SubprocessJobEnvelope(job=job, budgeted=job, session_id=f"session-{job_id}")


@pytest.fixture(autouse=True)
def _fake_cost_context(monkeypatch):
    # resolve_job_cost_context() reaches into the real container/catalog
    # (Postgres-backed in this repo's default wiring), which isn't available
    # in unit tests — stub it to a deterministic (profile_id, cost_rate).
    monkeypatch.setattr(
        "cys_core.infrastructure.execution.sandboxed_entrypoint.resolve_job_cost_context",
        lambda budgeted, *, default_cost_rate=0.003: ("cybersec-soc", 0.003),
    )
    yield


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_sandboxed_job_happy_path_configures_and_clears_budget():
    envelope = _envelope()
    run_worker_job = FakeRunWorkerJob(checks_budget_configured=True)
    metrics = FakeMetrics()
    tool_chain_policy = FakeToolChainPolicy()

    result = await execute_sandboxed_job(
        envelope,
        run_worker_job=run_worker_job,
        metrics=metrics,
        tool_chain_policy=tool_chain_policy,
        job_timeout=10.0,
        soft_timeout=5.0,
        default_cost_rate=0.003,
    )

    assert result.success is True
    # Discovery D: JobBudgetTracker must be configured *before* execute() runs
    # in this process, not just in the (separate) parent process.
    assert run_worker_job.budget_was_configured_during_execute is True
    # ...and cleared afterwards, same as WorkerOrchestrator.run_job's finally.
    assert JobBudgetTracker.get(envelope.session_id) is None
    assert tool_chain_policy.cleared == [envelope.job.job_id]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_sandboxed_job_soft_timeout_salvages():
    envelope = _envelope("j2")
    salvage = RunResult(job_id="j2", persona="soc", success=True, finding={"partial": True})
    run_worker_job = FakeRunWorkerJob(sleep_s=1.0, salvage_result=salvage)
    metrics = FakeMetrics()

    result = await execute_sandboxed_job(
        envelope,
        run_worker_job=run_worker_job,
        metrics=metrics,
        tool_chain_policy=FakeToolChainPolicy(),
        job_timeout=10.0,
        soft_timeout=0.05,
        default_cost_rate=0.003,
    )

    assert result is salvage
    run_worker_job.mark_job_timeout.assert_not_awaited()
    assert metrics.timeouts == []
    assert JobBudgetTracker.get(envelope.session_id) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_sandboxed_job_soft_timeout_without_salvage_marks_failure():
    envelope = _envelope("j3")
    run_worker_job = FakeRunWorkerJob(sleep_s=1.0, salvage_result=None)
    metrics = FakeMetrics()

    result = await execute_sandboxed_job(
        envelope,
        run_worker_job=run_worker_job,
        metrics=metrics,
        tool_chain_policy=FakeToolChainPolicy(),
        job_timeout=10.0,
        soft_timeout=0.05,
        default_cost_rate=0.003,
    )

    assert result.success is False
    assert result.error == "worker_job_timeout"
    run_worker_job.mark_job_timeout.assert_awaited_once_with(envelope.job)
    assert metrics.timeouts == ["soc"]
