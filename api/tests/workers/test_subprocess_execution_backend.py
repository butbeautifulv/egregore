from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.execution.subprocess_backend import SubprocessExecutionBackend

_FIXTURE = Path(__file__).parent / "fixtures" / "fake_sandboxed_job_child.py"


def _backend(mode: str) -> SubprocessExecutionBackend:
    return SubprocessExecutionBackend(command=[sys.executable, str(_FIXTURE), mode])


def _job(job_id: str = "j1") -> WorkerJob:
    return WorkerJob(job_id=job_id, event_id="e1", persona="soc", payload={"alert": "x"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subprocess_backend_parses_successful_child_result():
    backend = _backend("echo")
    job = _job()
    result = await backend.execute(job, job, "session-1", {})
    assert result.success is True
    assert result.job_id == "j1"
    assert result.persona == "soc"
    assert backend.owns_timeout is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subprocess_backend_propagates_child_reported_failure():
    backend = _backend("fail")
    result = await backend.execute(_job(), _job(), "session-1", {})
    assert result.success is False
    assert result.error == "simulated_failure"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subprocess_backend_handles_abnormal_exit_code():
    backend = _backend("crash")
    result = await backend.execute(_job(), _job(), "session-1", {})
    assert result.success is False
    assert result.error == "run_sandboxed_job_exit_2"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subprocess_backend_handles_unparseable_output():
    backend = _backend("garbage")
    result = await backend.execute(_job(), _job(), "session-1", {})
    assert result.success is False
    assert result.error == "run_sandboxed_job_unparseable_output"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subprocess_backend_reports_failure_when_child_logs_leak_to_stdout():
    """Regression for Discovery H.1 (docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md):
    the real production bug was a child that leaked structlog JSON lines onto
    stdout ahead of its final RunResult, breaking the single-JSON IPC
    contract. The real fix (configure_logging(stream=sys.stderr)) keeps a
    correct child's stdout clean, but this test locks in that *if* a child
    ever does leak extra lines again, the backend fails loud and
    predictable — `run_sandboxed_job_unparseable_output` — rather than
    crashing or silently losing the job. Before this fixture existed, that
    degradation path was only ever exercised by a live docker-compose run."""
    backend = _backend("noisy")
    result = await backend.execute(_job(), _job(), "session-1", {})
    assert result.success is False
    assert result.error == "run_sandboxed_job_unparseable_output"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subprocess_backend_kills_child_on_cancellation():
    import asyncio

    backend = _backend("hang")
    started = time.perf_counter()
    with pytest.raises((TimeoutError, asyncio.CancelledError)):
        await asyncio.wait_for(backend.execute(_job(), _job(), "session-1", {}), timeout=0.3)
    elapsed = time.perf_counter() - started
    # The fixture child sleeps for 3600s; if the backend didn't kill it on
    # cancellation, awaiting proc.communicate() in `finally` would block for
    # the same duration. Finishing quickly proves it was actually killed.
    assert elapsed < 5.0
