from __future__ import annotations

from typing import Any

from cys_core.application.ports.job_store import JobRecord, JobRecordSummary
from cys_core.domain.workers.models import PendingHitlAction, WorkerJob, WorkerJobStatus


class FakeJobStore:
    """Implements JobStorePort for enqueue tests."""

    name = "fake"

    def __init__(self) -> None:
        self.pending: list[str] = []

    def upsert_pending(self, job_id: str, persona: str, **kwargs: Any) -> JobRecord:
        self.pending.append(job_id)
        return JobRecord(
            job_id=job_id,
            session_id="",
            persona=persona,
            status=WorkerJobStatus.PENDING,
            correlation_id=str(kwargs.get("correlation_id", "")),
            tenant_id=str(kwargs.get("tenant_id", "default")),
            event_id=str(kwargs.get("event_id", "")),
        )

    def upsert_running(
        self,
        job_id: str,
        session_id: str,
        persona: str,
        **kwargs: Any,
    ) -> JobRecord:
        return JobRecord(
            job_id=job_id,
            session_id=session_id,
            persona=persona,
            correlation_id=str(kwargs.get("correlation_id", "")),
            tenant_id=str(kwargs.get("tenant_id", "default")),
            event_id=str(kwargs.get("event_id", "")),
        )

    def pause_for_hitl(self, pending: PendingHitlAction, preview: dict[str, Any]) -> JobRecord:
        return JobRecord(job_id=pending.job_id, session_id=pending.session_id, persona=pending.persona)

    def get(self, job_id: str) -> JobRecord | None:
        return None

    def mark_running(self, job_id: str) -> JobRecord | None:
        return None

    def mark_completed(self, job_id: str) -> None:
        return None

    def mark_failed(self, job_id: str) -> None:
        return None

    def list_pending_approvals(self) -> list[PendingHitlAction]:
        return []

    def list_by_investigation(self, tenant_id: str, investigation_id: str) -> list[JobRecordSummary]:
        return []

    def count_running(self) -> int:
        return 0

    def count_active_bus_jobs(self, tenant_id: str, engagement_id: str) -> int:
        return 0


class FakeJobQueue:
    """Implements JobQueueConnector for enqueue tests."""

    name = "fake"

    def __init__(self) -> None:
        self.jobs: list[WorkerJob] = []

    def enqueue(self, job: WorkerJob) -> str:
        self.jobs.append(job)
        return job.job_id

    def enqueue_front(self, job: WorkerJob) -> str:
        self.jobs.insert(0, job)
        return job.job_id

    def dequeue(self, timeout: float = 0.0) -> WorkerJob | None:
        if not self.jobs:
            return None
        return self.jobs.pop(0)

    async def aenqueue(self, job: WorkerJob) -> str:
        self.jobs.append(job)
        return job.job_id

    async def aenqueue_front(self, job: WorkerJob) -> str:
        self.jobs.insert(0, job)
        return job.job_id

    async def adequeue(self, timeout: float = 0.0) -> WorkerJob | None:
        return self.dequeue(timeout)

    async def aclose(self) -> None:
        return None

    def close(self) -> None:
        return None
