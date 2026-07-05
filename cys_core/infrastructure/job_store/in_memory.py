from __future__ import annotations

from typing import Any

from cys_core.application.ports.job_store import JobRecord, JobRecordSummary
from cys_core.domain.workers.models import PendingHitlAction, WorkerJobStatus


class InMemoryJobStore:
    """Process-local job status and HITL pause tracking."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def upsert_pending(
        self,
        job_id: str,
        persona: str,
        *,
        correlation_id: str = "",
        tenant_id: str = "default",
        event_id: str = "",
    ) -> JobRecord:
        record = JobRecord(
            job_id=job_id,
            session_id="",
            persona=persona,
            status=WorkerJobStatus.PENDING,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            event_id=event_id,
        )
        self._jobs[job_id] = record
        return record

    def upsert_running(
        self,
        job_id: str,
        session_id: str,
        persona: str,
        *,
        correlation_id: str = "",
        tenant_id: str = "default",
        event_id: str = "",
    ) -> JobRecord:
        existing = self._jobs.get(job_id)
        record = JobRecord(
            job_id=job_id,
            session_id=session_id,
            persona=persona,
            status=WorkerJobStatus.RUNNING,
            correlation_id=correlation_id or (existing.correlation_id if existing else ""),
            tenant_id=tenant_id or (existing.tenant_id if existing else "default"),
            event_id=event_id or (existing.event_id if existing else ""),
        )
        self._jobs[job_id] = record
        return record

    def pause_for_hitl(self, pending: PendingHitlAction, preview: dict[str, Any]) -> JobRecord:
        existing = self._jobs.get(pending.job_id)
        record = JobRecord(
            job_id=pending.job_id,
            session_id=pending.session_id,
            persona=pending.persona,
            status=WorkerJobStatus.AWAITING_APPROVAL,
            hitl_preview=preview,
            pending_hitl=pending,
            correlation_id=existing.correlation_id if existing else "",
            tenant_id=existing.tenant_id if existing else "default",
            event_id=existing.event_id if existing else "",
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

    def list_by_investigation(self, tenant_id: str, investigation_id: str) -> list[JobRecordSummary]:
        matches = [
            JobRecordSummary(
                job_id=record.job_id,
                session_id=record.session_id,
                persona=record.persona,
                status=record.status,
                correlation_id=record.correlation_id,
                tenant_id=record.tenant_id,
                event_id=record.event_id,
            )
            for record in self._jobs.values()
            if record.tenant_id == tenant_id and record.correlation_id == investigation_id
        ]
        return sorted(matches, key=lambda item: item.job_id)

    def count_running(self) -> int:
        return sum(1 for record in self._jobs.values() if record.status == WorkerJobStatus.RUNNING)

    def count_active_bus_jobs(self, tenant_id: str, engagement_id: str) -> int:
        active = {WorkerJobStatus.PENDING, WorkerJobStatus.RUNNING}
        return sum(
            1
            for record in self._jobs.values()
            if record.tenant_id == tenant_id
            and record.status in active
            and "-bus-" in record.job_id
            and engagement_id in record.correlation_id
        )
