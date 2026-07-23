from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg

from cys_core.application.ports.job_store import JobRecord, JobRecordSummary
from cys_core.domain.engagement.ids import normalize_correlation_id
from cys_core.domain.workers.models import PendingHitlAction, WorkerJobStatus
from cys_core.infrastructure.postgres_retry import connect_with_retry


def _follow_up_id_from_payload(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return None
        else:
            return None
    value = str(payload.get("follow_up_id") or "").strip()
    return value or None


_JOB_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS worker_jobs (
    job_id TEXT PRIMARY KEY,
    persona TEXT NOT NULL,
    event_id TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    tenant_id TEXT NOT NULL DEFAULT 'default',
    profile_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    session_id TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    hitl_preview_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    pending_hitl_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_worker_jobs_status ON worker_jobs (status);
CREATE INDEX IF NOT EXISTS idx_worker_jobs_correlation ON worker_jobs (tenant_id, correlation_id);
ALTER TABLE worker_jobs ADD COLUMN IF NOT EXISTS last_error TEXT NOT NULL DEFAULT '';
ALTER TABLE worker_jobs ADD COLUMN IF NOT EXISTS failure_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE worker_jobs ADD COLUMN IF NOT EXISTS profile_id TEXT NOT NULL DEFAULT '';
"""


class PostgresJobStore:
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url
        self._ensure_schema()

    def _connect(self) -> psycopg.Connection:
        return connect_with_retry(self._postgres_url)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_JOB_SCHEMA_SQL)
            conn.commit()

    def _row_to_record(self, row: tuple[Any, ...]) -> JobRecord:
        pending = PendingHitlAction.model_validate(row[8]) if row[8] else None
        preview = row[7] if isinstance(row[7], dict) else json.loads(row[7] or "{}")
        return JobRecord(
            job_id=row[0],
            session_id=row[1],
            persona=row[2],
            status=WorkerJobStatus(row[3]),
            correlation_id=row[4] or "",
            tenant_id=row[5] or "default",
            event_id=row[6] or "",
            profile_id=row[11] or "",
            hitl_preview=preview,
            pending_hitl=pending,
            last_error=str(row[9] or ""),
            failure_reason=str(row[10] or ""),
        )

    def _upsert(
        self,
        *,
        job_id: str,
        session_id: str,
        persona: str,
        status: WorkerJobStatus,
        hitl_preview: dict[str, Any] | None = None,
        pending_hitl: PendingHitlAction | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
        event_id: str = "",
        profile_id: str = "",
        last_error: str | None = None,
        failure_reason: str | None = None,
    ) -> JobRecord:
        existing = self.get(job_id)
        preview = hitl_preview if hitl_preview is not None else (existing.hitl_preview if existing else {})
        pending_json = pending_hitl.model_dump(mode="json") if pending_hitl else None
        resolved_correlation = correlation_id or (existing.correlation_id if existing else "")
        resolved_correlation = normalize_correlation_id(resolved_correlation)
        resolved_tenant = tenant_id or (existing.tenant_id if existing else "default")
        resolved_event = event_id or (existing.event_id if existing else "")
        resolved_profile = profile_id or (existing.profile_id if existing else "")
        resolved_error = last_error if last_error is not None else (existing.last_error if existing else "")
        resolved_reason = (
            failure_reason if failure_reason is not None else (existing.failure_reason if existing else "")
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO worker_jobs (
                    job_id, persona, status, session_id, correlation_id, tenant_id, event_id, profile_id,
                    hitl_preview_json, pending_hitl_json, last_error, failure_reason, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, NOW())
                ON CONFLICT (job_id) DO UPDATE SET
                    persona = EXCLUDED.persona,
                    status = EXCLUDED.status,
                    session_id = EXCLUDED.session_id,
                    correlation_id = EXCLUDED.correlation_id,
                    tenant_id = EXCLUDED.tenant_id,
                    event_id = EXCLUDED.event_id,
                    profile_id = EXCLUDED.profile_id,
                    hitl_preview_json = EXCLUDED.hitl_preview_json,
                    pending_hitl_json = EXCLUDED.pending_hitl_json,
                    last_error = EXCLUDED.last_error,
                    failure_reason = EXCLUDED.failure_reason,
                    updated_at = NOW()
                """,
                (
                    job_id,
                    persona,
                    status.value,
                    session_id,
                    resolved_correlation,
                    resolved_tenant,
                    resolved_event,
                    resolved_profile,
                    json.dumps(preview),
                    json.dumps(pending_json),
                    (resolved_error or "")[:500],
                    (resolved_reason or "")[:120],
                ),
            )
            conn.commit()
        return JobRecord(
            job_id=job_id,
            session_id=session_id,
            persona=persona,
            status=status,
            hitl_preview=preview,
            pending_hitl=pending_hitl,
            correlation_id=resolved_correlation,
            tenant_id=resolved_tenant,
            event_id=resolved_event,
            profile_id=resolved_profile,
            last_error=(resolved_error or "")[:500],
            failure_reason=(resolved_reason or "")[:120],
        )

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
        return self._upsert(
            job_id=job_id,
            session_id="",
            persona=persona,
            status=WorkerJobStatus.PENDING,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
           event_id=event_id,
            profile_id=profile_id,
        )

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
        return self._upsert(
            job_id=job_id,
            session_id=session_id,
            persona=persona,
            status=WorkerJobStatus.RUNNING,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            event_id=event_id,
            profile_id=profile_id,
        )

    def pause_for_hitl(self, pending: PendingHitlAction, preview: dict[str, Any]) -> JobRecord:
        existing = self.get(pending.job_id)
        return self._upsert(
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

    def get(self, job_id: str) -> JobRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, session_id, persona, status, correlation_id, tenant_id, event_id,
                       hitl_preview_json, pending_hitl_json, last_error, failure_reason, profile_id
                FROM worker_jobs WHERE job_id = %s
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def mark_running(self, job_id: str) -> JobRecord | None:
        record = self.get(job_id)
        if record is None:
            return None
        return self._upsert(
            job_id=job_id,
            session_id=record.session_id,
            persona=record.persona,
            status=WorkerJobStatus.RUNNING,
            hitl_preview=record.hitl_preview,
            pending_hitl=None,
            correlation_id=record.correlation_id,
            tenant_id=record.tenant_id,
            event_id=record.event_id,
            profile_id=record.profile_id,
        )

    def mark_completed(self, job_id: str) -> None:
        record = self.get(job_id)
        if record is None:
            return
        self._upsert(
            job_id=job_id,
            session_id=record.session_id,
            persona=record.persona,
            status=WorkerJobStatus.COMPLETED,
            hitl_preview=record.hitl_preview,
            correlation_id=record.correlation_id,
            tenant_id=record.tenant_id,
            event_id=record.event_id,
            profile_id=record.profile_id,
        )

    def mark_failed(self, job_id: str, *, error: str = "", reason: str = "") -> None:
        record = self.get(job_id)
        if record is None:
            return
        self._upsert(
            job_id=job_id,
            session_id=record.session_id,
            persona=record.persona,
            status=WorkerJobStatus.FAILED,
            hitl_preview=record.hitl_preview,
            correlation_id=record.correlation_id,
            tenant_id=record.tenant_id,
            event_id=record.event_id,
            profile_id=record.profile_id,
            last_error=(error or "")[:500],
            failure_reason=(reason or "")[:120],
        )

    def list_pending_approvals(self) -> list[PendingHitlAction]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT pending_hitl_json FROM worker_jobs
                WHERE status = %s AND pending_hitl_json IS NOT NULL
                """,
                (WorkerJobStatus.AWAITING_APPROVAL.value,),
            ).fetchall()
        result: list[PendingHitlAction] = []
        for row in rows:
            if row[0]:
                result.append(PendingHitlAction.model_validate(row[0]))
        return result

    def list_by_investigation(self, tenant_id: str, investigation_id: str) -> list[JobRecordSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id, session_id, persona, status, correlation_id, tenant_id, event_id, created_at,
                       payload_json, last_error, failure_reason
                FROM worker_jobs
                WHERE tenant_id = %s AND correlation_id = %s
                ORDER BY created_at ASC
                """,
                (tenant_id, investigation_id),
            ).fetchall()
        return [
            JobRecordSummary(
                job_id=row[0],
                session_id=row[1],
                persona=row[2],
                status=WorkerJobStatus(row[3]),
                correlation_id=row[4] or "",
                tenant_id=row[5] or "default",
                event_id=row[6] or "",
                created_at=row[7].isoformat() if row[7] is not None else "",
                follow_up_id=_follow_up_id_from_payload(row[8]),
                last_error=str(row[9] or ""),
                failure_reason=str(row[10] or ""),
            )
            for row in rows
        ]

    def count_running(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM worker_jobs WHERE status = %s",
                (WorkerJobStatus.RUNNING.value,),
            ).fetchone()
        return int(row[0]) if row else 0

    def count_active_bus_jobs(self, tenant_id: str, engagement_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM worker_jobs
                WHERE tenant_id = %s
                  AND job_id ~ '^[a-z][a-z0-9]*-bus-'
                  AND status IN (%s, %s)
                  AND correlation_id LIKE %s
                """,
                (
                    tenant_id,
                    WorkerJobStatus.PENDING.value,
                    WorkerJobStatus.RUNNING.value,
                    f"%{engagement_id}%",
                ),
            ).fetchone()
        return int(row[0]) if row else 0

    def _summary_from_bus_row(self, row: tuple[Any, ...]) -> JobRecordSummary:
        return JobRecordSummary(
            job_id=row[0],
            session_id=row[1],
            persona=row[2],
            status=WorkerJobStatus(row[3]),
            correlation_id=row[4] or "",
            tenant_id=row[5] or "default",
            event_id=row[6] or "",
            created_at=row[7].isoformat() if row[7] is not None else "",
            updated_at=row[8].isoformat() if row[8] is not None else "",
            follow_up_id=_follow_up_id_from_payload(row[9]),
            last_error=str(row[10] or ""),
            failure_reason=str(row[11] or ""),
        )

    def list_active_bus_jobs(self, tenant_id: str, engagement_id: str) -> list[JobRecordSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id, session_id, persona, status, correlation_id, tenant_id, event_id,
                       created_at, updated_at, payload_json, last_error, failure_reason
                FROM worker_jobs
                WHERE tenant_id = %s
                  AND job_id ~ '^[a-z][a-z0-9]*-bus-'
                  AND status IN (%s, %s)
                  AND correlation_id LIKE %s
                ORDER BY updated_at ASC
                """,
                (
                    tenant_id,
                    WorkerJobStatus.PENDING.value,
                    WorkerJobStatus.RUNNING.value,
                    f"%{engagement_id}%",
                ),
            ).fetchall()
        return [self._summary_from_bus_row(row) for row in rows]

    def list_stale_bus_jobs(
        self,
        tenant_id: str,
        engagement_id: str,
        *,
        older_than_s: float,
    ) -> list[JobRecordSummary]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_s)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id, session_id, persona, status, correlation_id, tenant_id, event_id,
                       created_at, updated_at, payload_json, last_error, failure_reason
                FROM worker_jobs
                WHERE tenant_id = %s
                  AND job_id ~ '^[a-z][a-z0-9]*-bus-'
                  AND status IN (%s, %s)
                  AND correlation_id LIKE %s
                  AND updated_at < %s
                """,
                (
                    tenant_id,
                    WorkerJobStatus.PENDING.value,
                    WorkerJobStatus.RUNNING.value,
                    f"%{engagement_id}%",
                    cutoff,
                ),
            ).fetchall()
        return [self._summary_from_bus_row(row) for row in rows]
