from __future__ import annotations

import pytest

from cys_core.domain.workers.models import DEFAULT_BUDGET, WorkerJob, WorkerJobStatus


@pytest.mark.unit
def test_worker_job_transition_valid() -> None:
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc")
    job.transition_to(WorkerJobStatus.RUNNING)
    job.transition_to(WorkerJobStatus.COMPLETED)
    assert job.status == WorkerJobStatus.COMPLETED


@pytest.mark.unit
def test_worker_job_transition_invalid_raises() -> None:
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc")
    with pytest.raises(ValueError, match="invalid job status transition"):
        job.transition_to(WorkerJobStatus.COMPLETED)


@pytest.mark.unit
def test_apply_budget_fills_missing_limits() -> None:
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc")
    budgeted = job.apply_budget(DEFAULT_BUDGET)
    assert budgeted.max_tokens == DEFAULT_BUDGET.max_tokens
    assert budgeted.max_cost_usd == DEFAULT_BUDGET.max_cost_usd
