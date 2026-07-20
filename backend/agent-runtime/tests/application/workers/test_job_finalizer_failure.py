from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.workers.job_finalizer import WorkerJobFinalizer
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.workers.exceptions import JobBudgetExceeded
from cys_core.domain.workers.failure_reason import WorkerJobFailureReason
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus


def _job() -> WorkerJob:
    return WorkerJob(
        job_id="job-1",
        persona="soc",
        tenant_id="tenant-1",
        event_id="eng-1",
        correlation_id="eng-1",
        payload={},
    )


@pytest.fixture
def finalizer() -> tuple[WorkerJobFinalizer, MagicMock, list[tuple[str, str]]]:
    egress = MagicMock()
    failures: list[tuple[str, str]] = []

    fin = WorkerJobFinalizer(
        job_store=MagicMock(),
        queue=MagicMock(),
        bus=MagicMock(),
        agent_catalog=MagicMock(),
        engagement_store=MagicMock(),
        engagement_egress=egress,
        record_worker_job_failure=lambda persona, reason: failures.append((persona, reason)),
    )
    fin._queue.send_to_dlq = AsyncMock()
    return fin, egress, failures


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finalize_failure_emits_job_finished_with_reason(
    finalizer: tuple[WorkerJobFinalizer, MagicMock, list[tuple[str, str]]],
) -> None:
    fin, egress, failures = finalizer
    job = _job()

    reason = await fin.finalize_failure(job, error_string="ungrounded_finding:missing obs_id")

    assert reason == WorkerJobFailureReason.GROUNDING_REJECTED
    assert job.status == WorkerJobStatus.FAILED
    finished_calls = [c for c in egress.publish_status.call_args_list if c.args[1] == "job_finished"]
    assert len(finished_calls) == 1
    payload = finished_calls[0].args[2]
    assert payload["success"] is False
    assert payload["reason"] == "grounding_rejected"
    assert failures == [("soc", "grounding_rejected")]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mark_budget_failure_emits_budget_exceeded_and_job_finished(
    finalizer: tuple[WorkerJobFinalizer, MagicMock, list[tuple[str, str]]],
) -> None:
    fin, egress, failures = finalizer
    job = _job()

    await fin.mark_budget_failure(job, exc=JobBudgetExceeded("tool budget"))

    finished_calls = [c for c in egress.publish_status.call_args_list if c.args[1] == "job_finished"]
    assert len(finished_calls) == 1
    egress.publish_event.assert_called_once()
    event_type = egress.publish_event.call_args.args[1]
    assert event_type == "budget_exceeded"
    assert failures == [("soc", "budget_exceeded")]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mark_security_failure_records_sanitizer_and_reason(
    finalizer: tuple[WorkerJobFinalizer, MagicMock, list[tuple[str, str]]],
) -> None:
    fin, egress, failures = finalizer
    blocks: list[tuple[str, str]] = []
    fin._record_sanitizer_block = lambda where, mode: blocks.append((where, mode))
    job = _job()

    await fin.mark_security_failure(job, exc=SecurityViolation("blocked input"))

    finished_calls = [c for c in egress.publish_status.call_args_list if c.args[1] == "job_finished"]
    payload = finished_calls[0].args[2]
    assert payload["reason"] == "security_violation"
    assert blocks == [("worker", "hard")]
    assert failures == [("soc", "security_violation")]
