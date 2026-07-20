from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.domain.workers.models import WorkerJob
from tests.application.workers.factory import build_run_worker_job_for_tests


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_worker_job_resume_branch_calls_aresume_and_publishes():
    """RunWorkerJob.execute()'s resume branch (6.3) — continues the original
    LangGraph thread via aresume(), not a fresh arun(), with a real sandbox
    scoped to the resume job's own run_id."""
    aresume = AsyncMock(return_value={"summary": "resumed ok"})
    run_worker_job = build_run_worker_job_for_tests(runtime=SimpleNamespace(aresume=aresume))

    resume_job = WorkerJob(
        job_id="resume-job-1",
        event_id="job-1",
        persona="soc",
        resume_checkpoint_ref="worker:soc:job-1",
        payload={"decision": "approve", "approval_id": "appr-1"},
    )

    result = await run_worker_job.execute(resume_job, resume_job, "worker:soc:job-1", {})

    assert result.success is True
    assert result.finding == {"summary": "resumed ok"}
    aresume.assert_awaited_once_with("soc", "worker:soc:job-1", {"decision": "approve", "approval_id": "appr-1"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_worker_job_resume_branch_marks_failure_on_error():
    aresume = AsyncMock(side_effect=RuntimeError("graph blew up"))
    run_worker_job = build_run_worker_job_for_tests(runtime=SimpleNamespace(aresume=aresume))

    resume_job = WorkerJob(
        job_id="resume-job-2",
        event_id="job-2",
        persona="soc",
        resume_checkpoint_ref="worker:soc:job-2",
        payload={"decision": "approve", "approval_id": "appr-1"},
    )

    result = await run_worker_job.execute(resume_job, resume_job, "worker:soc:job-2", {})

    assert result.success is False
    assert "graph blew up" in result.error
