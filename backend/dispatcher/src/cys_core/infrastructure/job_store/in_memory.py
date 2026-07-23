from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from cys_core.application.ports.job_store import JobRecord, JobRecordSummary
from cys_core.domain.engagement.ids import normalize_correlation_id
from cys_core.domain.workers.bus_job_ids import is_bus_worker_job_id
from cys_core.domain.workers.models import PendingHitlAction, WorkerJobStatus


class InMemoryJobStore:
    """Process-local job status and HITL pause tracking."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._updated_at: dict[str, datetime] = {}

    def _touch(self, job_id: str) -> None:
        self._updated_at[job_id] = datetime.now(timezone.utc)

    def _normalized_correlation(self, correlation_id: str) -> str:
        return normalize_correlation_id(correlation_id)

    def upsert_pending(
        self,
        job_id: str,
        persona: str,
        *,
        correlation_id: str = "",
        tenant_id: str = "default",
        event_id: str = "",
        profile_id: str = "",
    ) -> JobRecord:
        record = JobRecord(
            job_id=job_id,
            session_id="",
            persona=persona,
            status=WorkerJobStatus.PENDING,
            correlation_id=self._normalized_correlation(correlation_id),
            tenant_id=tenant_id,
            event_id=event_id,
            profile_id=profile_id,
        )
        self._jobs[job_id] = record
        self._touch(job_id)
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
        profile_id: str = "",
    ) -> JobRecord:
        existing = self._jobs.get(job_id)
        record = JobRecord(
            job_id=job_id,
            session_id=session_id,
            persona=persona,
            status=WorkerJobStatus.RUNNING,
            correlation_id=self._normalized_correlation(
                correlation_id or (existing.correlation_id if existing else "")
            ),
            tenant_id=tenant_id or (existing.tenant_id if existing else "default"),
            event_id=event_id or (existing.event_id if existing else ""),
            profile_id=profile_id or (existing.profile_id if existing else ""),
        )
        self._jobs[job_id] = record
        self._touch(job_id)
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
            profile_id=existing.profile_id if existing else "",
        )
        self._jobs[pending.job_id] = record
        self._touch(pending.job_id)
        return record

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def mark_running(self, job_id: str) -> JobRecord | None:
        record = self._jobs.get(job_id)
        if record is None:
            return None
        record.status = WorkerJobStatus.RUNNING
        record.pending_hitl = None
        self._touch(job_id)
        return record

    def mark_completed(self, job_id: str) -> None:
        record = self._jobs.get(job_id)
        if record is not None:
            record.status = WorkerJobStatus.COMPLETED
            self._touch(job_id)

    def mark_failed(self, job_id: str, *, error: str = "", reason: str = "") -> None:
        record = self._jobs.get(job_id)
        if record is not None:
            record.status = WorkerJobStatus.FAILED
            record.last_error = (error or "")[:500]
            record.failure_reason = (reason or "")[:120]
            self._touch(job_id)

    def list_pending_approvals(self) -> list[PendingHitlAction]:
        return [
            record.pending_hitl
            for record in self._jobs.values()
            if record.status == WorkerJobStatus.AWAITING_APPROVAL and record.pending_hitl is not None
        ]

    def _to_summary(self, record: JobRecord) -> JobRecordSummary:
        updated = self._updated_at.get(record.job_id)
        return JobRecordSummary(
            job_id=record.job_id,
            session_id=record.session_id,
            persona=record.persona,
            status=record.status,
            correlation_id=record.correlation_id,
            tenant_id=record.tenant_id,
            event_id=record.event_id,
            profile_id=record.profile_id,
            updated_at=updated.isoformat() if updated is not None else "",
            last_error=record.last_error,
            failure_reason=record.failure_reason,
        )

    def _matches_engagement(self, record: JobRecord, tenant_id: str, engagement_id: str) -> bool:
        return record.tenant_id == tenant_id and engagement_id in record.correlation_id

    def list_by_investigation(self, tenant_id: str, investigation_id: str) -> list[JobRecordSummary]:
        matches = [
            self._to_summary(record)
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
            if record.status in active
            and is_bus_worker_job_id(record.job_id)
            and self._matches_engagement(record, tenant_id, engagement_id)
        )

    def list_active_bus_jobs(self, tenant_id: str, engagement_id: str) -> list[JobRecordSummary]:
        active = {WorkerJobStatus.PENDING, WorkerJobStatus.RUNNING}
        matches = [
            self._to_summary(record)
            for record in self._jobs.values()
            if record.status in active
            and is_bus_worker_job_id(record.job_id)
            and self._matches_engagement(record, tenant_id, engagement_id)
        ]
        return sorted(matches, key=lambda item: item.job_id)

    def list_stale_bus_jobs(
        self,
        tenant_id: str,
        engagement_id: str,
        *,
        older_than_s: float,
    ) -> list[JobRecordSummary]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_s)
        active = {WorkerJobStatus.PENDING, WorkerJobStatus.RUNNING}
        matches: list[JobRecordSummary] = []
        for record in self._jobs.values():
            if record.status not in active or not is_bus_worker_job_id(record.job_id):
                continue
            if not self._matches_engagement(record, tenant_id, engagement_id):
                continue
            updated = self._updated_at.get(record.job_id)
            if updated is None or updated >= cutoff:
                continue
            matches.append(self._to_summary(record))
        return sorted(matches, key=lambda item: item.job_id)
