from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus
from cys_core.infrastructure.execution.k8s_backend import K8sExecutionBackend


@dataclass
class _FakeJobRecord:
    status: WorkerJobStatus
    last_error: str = ""
    failure_reason: str = ""


class _FakeJobStore:
    def __init__(self, records_by_call: list[_FakeJobRecord | None]) -> None:
        self._records = list(records_by_call)
        self.calls = 0

    def get(self, job_id: str):
        self.calls += 1
        if self._records:
            return self._records.pop(0) if len(self._records) > 1 else self._records[0]
        return None


def _job(job_id: str = "j1") -> WorkerJob:
    return WorkerJob(job_id=job_id, event_id="e1", persona="soc", payload={"alert": "x"})


def _backend(*, job_store, batch_api=None, poll_interval_s=0.01) -> K8sExecutionBackend:
    return K8sExecutionBackend(
        job_store=job_store,
        namespace="egregore",
        image="egregore-worker:latest",
        job_timeout_resolver=lambda job: 1.0,
        batch_api=batch_api or MagicMock(),
        poll_interval_s=poll_interval_s,
    )


@pytest.mark.unit
def test_owns_timeout_is_true():
    assert K8sExecutionBackend.owns_timeout is True


@pytest.mark.unit
async def test_job_spec_runs_run_sandboxed_job_not_daemon():
    """Phase 3.0/3.1 fix: the pod must run this specific job, not a
    queue-draining worker.daemon that could pick up any job."""
    batch_api = MagicMock()
    job_store = _FakeJobStore([_FakeJobRecord(WorkerJobStatus.COMPLETED)])
    backend = _backend(job_store=job_store, batch_api=batch_api)
    job = _job()

    await backend._run_async(job, job, "session-1", job_timeout=1.0)

    _, kwargs = batch_api.create_namespaced_job.call_args
    body = kwargs["body"]
    container = body["spec"]["template"]["spec"]["containers"][0]
    assert container["args"] == [
        "uv",
        "run",
        "egregore",
        "run-sandboxed-job",
        "--job-json",
        "env:JOB_PAYLOAD_JSON",
    ]
    env = {e["name"]: e["value"] for e in container["env"]}
    assert env["K8S_SANDBOX_CREDENTIALS_ONLY"] == "true"
    envelope = json.loads(env["JOB_PAYLOAD_JSON"])
    assert envelope["job"]["job_id"] == job.job_id
    assert envelope["session_id"] == "session-1"


@pytest.mark.unit
async def test_deletes_job_after_completion():
    batch_api = MagicMock()
    job_store = _FakeJobStore([_FakeJobRecord(WorkerJobStatus.COMPLETED)])
    backend = _backend(job_store=job_store, batch_api=batch_api)

    result = await backend._run_async(_job(), _job(), "session-1", job_timeout=1.0)

    assert result.success is True
    batch_api.delete_namespaced_job.assert_called_once()


@pytest.mark.unit
async def test_failed_job_record_produces_failed_result():
    job_store = _FakeJobStore(
        [_FakeJobRecord(WorkerJobStatus.FAILED, last_error="boom", failure_reason="worker_job_timeout")]
    )
    backend = _backend(job_store=job_store)

    result = await backend._run_async(_job("j2"), _job("j2"), "session-1", job_timeout=1.0)

    assert result.success is False
    assert result.error == "boom"


@pytest.mark.unit
async def test_polling_times_out_if_never_terminal():
    job_store = _FakeJobStore([None])
    backend = _backend(job_store=job_store, poll_interval_s=0.01)

    with pytest.raises(TimeoutError):
        await backend._run_async(_job("j3"), _job("j3"), "session-1", job_timeout=0.05)


@pytest.mark.unit
async def test_no_batch_api_raises_instead_of_running_unsandboxed():
    backend = K8sExecutionBackend(
        job_store=_FakeJobStore([]),
        namespace="egregore",
        image="egregore-worker:latest",
        job_timeout_resolver=lambda job: 1.0,
        batch_api=None,
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        await backend._run_async(_job(), _job(), "session-1", job_timeout=1.0)


@pytest.mark.unit
async def test_sets_runtime_class_when_configured():
    batch_api = MagicMock()
    job_store = _FakeJobStore([_FakeJobRecord(WorkerJobStatus.COMPLETED)])
    backend = K8sExecutionBackend(
        job_store=job_store,
        namespace="egregore",
        image="egregore-worker:latest",
        job_timeout_resolver=lambda job: 1.0,
        batch_api=batch_api,
        runtime_class="gvisor",
    )

    await backend._run_async(_job(), _job(), "session-1", job_timeout=1.0)

    _, kwargs = batch_api.create_namespaced_job.call_args
    pod_spec = kwargs["body"]["spec"]["template"]["spec"]
    assert pod_spec["runtimeClassName"] == "gvisor"


@pytest.mark.unit
async def test_omits_runtime_class_when_unset():
    batch_api = MagicMock()
    job_store = _FakeJobStore([_FakeJobRecord(WorkerJobStatus.COMPLETED)])
    backend = _backend(job_store=job_store, batch_api=batch_api)

    await backend._run_async(_job(), _job(), "session-1", job_timeout=1.0)

    _, kwargs = batch_api.create_namespaced_job.call_args
    pod_spec = kwargs["body"]["spec"]["template"]["spec"]
    assert "runtimeClassName" not in pod_spec
