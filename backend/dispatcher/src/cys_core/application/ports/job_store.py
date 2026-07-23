from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from cys_core.domain.workers.models import PendingHitlAction, WorkerJobStatus


@dataclass
class JobRecord:
    job_id: str
    session_id: str
    persona: str
    status: WorkerJobStatus = WorkerJobStatus.RUNNING
    hitl_preview: dict[str, Any] = field(default_factory=dict)
    pending_hitl: PendingHitlAction | None = None
    correlation_id: str = ""
    tenant_id: str = "default"
    event_id: str = ""
    profile_id: str = ""
    last_error: str = ""
    failure_reason: str = ""


@dataclass
class JobRecordSummary:
    job_id: str
    session_id: str
    persona: str
    status: WorkerJobStatus
    correlation_id: str = ""
    tenant_id: str = "default"
    event_id: str = ""
    profile_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    follow_up_id: str | None = None
    last_error: str = ""
    failure_reason: str = ""


class JobStorePort(Protocol):
    def upsert_pending(
        self,
        job_id: str,
        persona: str,
        *,
        correlation_id: str = "",
        tenant_id: str = "default",
        event_id: str = "",
        profile_id: str = "",
    ) -> JobRecord: ...

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
    ) -> JobRecord: ...

    def pause_for_hitl(self, pending: PendingHitlAction, preview: dict[str, Any]) -> JobRecord: ...

    def get(self, job_id: str) -> JobRecord | None: ...

    def mark_running(self, job_id: str) -> JobRecord | None: ...

    def mark_completed(self, job_id: str) -> None: ...

    def mark_failed(self, job_id: str, *, error: str = "", reason: str = "") -> None: ...

    def list_pending_approvals(self) -> list[PendingHitlAction]: ...

    def list_by_investigation(self, tenant_id: str, investigation_id: str) -> list[JobRecordSummary]: ...

    def count_running(self) -> int: ...

    def count_active_bus_jobs(self, tenant_id: str, engagement_id: str) -> int: ...

    def list_active_bus_jobs(self, tenant_id: str, engagement_id: str) -> list[JobRecordSummary]: ...

    def list_stale_bus_jobs(
        self,
        tenant_id: str,
        engagement_id: str,
        *,
        older_than_s: float,
    ) -> list[JobRecordSummary]: ...
