from __future__ import annotations

from typing import Any

from cys_core.domain.workers.models import RunResult, WorkerJob


class InProcessExecutionBackend:
    """Runs the job's execute() call in the same process as the Dispatcher.

    This is today's behavior, extracted behind the ExecutionBackend port so
    later backends (subprocess, K8s, Docker) can be swapped in without
    touching WorkerOrchestrator's budget/timeout/salvage logic.

    ``run_worker_job`` is typed as ``Any`` rather than the concrete
    ``RunWorkerJob`` (cys_core.application.use_cases) deliberately —
    infrastructure adapters must not import application/use_cases directly
    (hexagon inversion, enforced by scripts/verify_import_boundaries.py); this
    class only relies on it having an ``execute(...)`` method matching
    ExecutionBackend's own signature.
    """

    owns_timeout = False

    def __init__(self, run_worker_job: Any) -> None:
        self._run_worker_job = run_worker_job

    async def execute(
        self,
        job: WorkerJob,
        budgeted: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
    ) -> RunResult:
        return await self._run_worker_job.execute(job, budgeted, session_id, job_state)
