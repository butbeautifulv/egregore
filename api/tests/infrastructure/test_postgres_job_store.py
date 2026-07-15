from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any

import pytest

from cys_core.domain.workers.models import PendingHitlAction, WorkerJobStatus
from cys_core.infrastructure.job_store.postgres import PostgresJobStore


class _FakeCursor:
    def __init__(self, conn: "_FakeConnection") -> None:
        self._conn = conn
        self._rows: list[tuple[Any, ...]] = []

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self._conn.run(sql, params or ())


class _FakeConnection:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.migrations: set[str] = set()

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> _FakeCursor:
        cursor = _FakeCursor(self)
        cursor.execute(sql, params or ())
        if "SELECT pending_hitl_json FROM worker_jobs" in sql:
            cursor._rows = [
                (row["pending_hitl_json"],)
                for row in self.jobs.values()
                if row["status"] == WorkerJobStatus.AWAITING_APPROVAL.value and row["pending_hitl_json"]
            ]
        elif "SELECT job_id, session_id, persona, status" in sql:
            job_id = params[0] if params else ""
            row = self.jobs.get(job_id)
            if row is not None:
                cursor._rows = [
                    (
                        row["job_id"],
                        row["session_id"],
                        row["persona"],
                        row["status"],
                        row.get("correlation_id", ""),
                        row.get("tenant_id", "default"),
                        row.get("event_id", ""),
                        row["hitl_preview_json"],
                        row["pending_hitl_json"],
                    )
                ]
        return cursor

    def run(self, sql: str, params: tuple[Any, ...]) -> None:
        if sql.strip().startswith("CREATE TABLE"):
            return
        if "INSERT INTO worker_jobs" in sql:
            (
                job_id,
                persona,
                status,
                session_id,
                correlation_id,
                tenant_id,
                event_id,
                preview,
                pending,
            ) = params
            pending_data = json.loads(pending) if pending else None
            self.jobs[job_id] = {
                "job_id": job_id,
                "persona": persona,
                "status": status,
                "session_id": session_id,
                "correlation_id": correlation_id,
                "tenant_id": tenant_id,
                "event_id": event_id,
                "hitl_preview_json": json.loads(preview),
                "pending_hitl_json": pending_data,
            }

    def commit(self) -> None:
        return

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return


@pytest.mark.unit
def test_postgres_job_store_roundtrip(monkeypatch):
    fake = _FakeConnection()

    @contextmanager
    def _connect():
        yield fake

    monkeypatch.setattr("cys_core.infrastructure.job_store.postgres.psycopg.connect", lambda _url: fake)
    store_a = PostgresJobStore("postgresql://test")
    store_a.upsert_running("job-1", "worker:soc:job-1", "soc")
    pending = PendingHitlAction(
        job_id="job-1",
        session_id="worker:soc:job-1",
        persona="soc",
        tool_name="run_active_scan",
        tool_args={"target": "example.com"},
        approval_id="appr-1",
    )
    store_a.pause_for_hitl(pending, {"tool": "run_active_scan"})

    store_b = PostgresJobStore("postgresql://test")
    record = store_b.get("job-1")
    assert record is not None
    assert record.status == WorkerJobStatus.AWAITING_APPROVAL
    assert len(store_b.list_pending_approvals()) == 1
