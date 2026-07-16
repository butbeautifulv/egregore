from __future__ import annotations

import pytest

from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.execution.in_process import InProcessExecutionBackend
from tests.application.workers.factory import build_run_worker_job_for_tests


def _job(job_id: str) -> WorkerJob:
    return WorkerJob(job_id=job_id, event_id="e1", persona="soc", payload={"alert": "x"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_in_process_backend_matches_direct_execute_call():
    """Golden/parity test: swapping in the ExecutionBackend port must not change
    RunWorkerJob.execute's outcome. Two independent job instances (not the same
    job_id — several worker submodules key state by job_id) so calling execute
    twice can't contaminate itself."""
    run_worker_job = build_run_worker_job_for_tests()
    direct_result = await run_worker_job.execute(_job("direct-1"), _job("direct-1"), "session-direct", {})

    backend = InProcessExecutionBackend(run_worker_job)
    backend_result = await backend.execute(_job("backend-1"), _job("backend-1"), "session-backend", {})

    assert backend_result.success == direct_result.success
    assert backend_result.finding == direct_result.finding
    assert backend_result.error == direct_result.error
    assert backend_result.sandbox_id == direct_result.sandbox_id
