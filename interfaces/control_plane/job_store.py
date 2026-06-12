from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cys_core.domain.workers.models import PendingHitlAction, WorkerJobStatus


@dataclass
class JobRecord:
    job_id: str
    session_id: str
    persona: str
    status: WorkerJobStatus = WorkerJobStatus.RUNNING
    hitl_preview: dict[str, Any] = field(default_factory=dict)
    pending_hitl: PendingHitlAction | None = None


class JobStore:
    """In-memory job status and HITL pause tracking."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def upsert_running(self, job_id: str, session_id: str, persona: str) -> JobRecord:
        record = JobRecord(job_id=job_id, session_id=session_id, persona=persona, status=WorkerJobStatus.RUNNING)
        self._jobs[job_id] = record
        return record

    def pause_for_hitl(self, pending: PendingHitlAction, preview: dict[str, Any]) -> JobRecord:
        record = JobRecord(
            job_id=pending.job_id,
            session_id=pending.session_id,
            persona=pending.persona,
            status=WorkerJobStatus.AWAITING_APPROVAL,
            hitl_preview=preview,
            pending_hitl=pending,
        )
        self._jobs[pending.job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def mark_running(self, job_id: str) -> JobRecord | None:
        record = self._jobs.get(job_id)
        if record is None:
            return None
        record.status = WorkerJobStatus.RUNNING
        record.pending_hitl = None
        return record

    def mark_completed(self, job_id: str) -> None:
        record = self._jobs.get(job_id)
        if record is not None:
            record.status = WorkerJobStatus.COMPLETED

    def mark_failed(self, job_id: str) -> None:
        record = self._jobs.get(job_id)
        if record is not None:
            record.status = WorkerJobStatus.FAILED

    def list_pending_approvals(self) -> list[PendingHitlAction]:
        return [
            record.pending_hitl
            for record in self._jobs.values()
            if record.status == WorkerJobStatus.AWAITING_APPROVAL and record.pending_hitl is not None
        ]


_job_store = JobStore()


def get_job_store() -> JobStore:
    return _job_store
