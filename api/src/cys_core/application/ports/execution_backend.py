from __future__ import annotations

from typing import Protocol

from cys_core.domain.workers.models import RunResult, WorkerJob


class ExecutionBackend(Protocol):
    """Port for where/how a worker job's agent execution actually runs.

    Signature mirrors ``RunWorkerJob.execute`` 1:1 so implementations can wrap
    it directly (in-process) or ship the same arguments across a process/
    container boundary (subprocess, K8s, Docker).
    """

    async def execute(
        self,
        job: WorkerJob,
        budgeted: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
    ) -> RunResult:
        """Execute the job and return its result."""
