from __future__ import annotations

from typing import Protocol

from cys_core.domain.workers.models import RunResult, WorkerJob


class ExecutionBackend(Protocol):
    """Port for where/how a worker job's agent execution actually runs.

    Signature mirrors ``RunWorkerJob.execute`` 1:1 so implementations can wrap
    it directly (in-process) or ship the same arguments across a process/
    container boundary (subprocess, K8s, Docker).
    """

    #: True for backends whose child process manages its own soft-timeout and
    #: salvage (subprocess/K8s/Docker) — the caller (WorkerOrchestrator.run_job)
    #: must then use a hard job_timeout dead-man's switch instead of racing its
    #: own soft-timeout against the child's, and must not attempt to salvage
    #: from its own (empty) tool_execution_tracker/JobBudgetTracker state. False
    #: for InProcessExecutionBackend, where today's soft-timeout+salvage in the
    #: caller is still correct because execute() runs in the same process.
    owns_timeout: bool

    async def execute(
        self,
        job: WorkerJob,
        budgeted: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
    ) -> RunResult:
        """Execute the job and return its result."""
