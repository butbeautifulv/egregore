from __future__ import annotations

from pydantic import BaseModel

from cys_core.domain.workers.models import WorkerJob


class SubprocessJobEnvelope(BaseModel):
    """Everything a `run-sandboxed-job` child process needs to execute a job
    the same way WorkerOrchestrator.run_job would have, without redoing
    Dispatcher-level work (dependency-deferral, budget enrichment) that
    already happened in the parent before it decided to spawn this child.

    profile_id, cost_rate, job_timeout, and soft_timeout are deliberately not
    included here — they're pure functions of job/budgeted plus shared
    settings/catalog state (see resolve_job_cost_context and
    Settings.resolve_worker_job_timeout), so the child recomputes them itself
    rather than trusting values shipped over the wire.
    """

    job: WorkerJob
    budgeted: WorkerJob
    session_id: str
