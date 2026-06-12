from __future__ import annotations

import json
from typing import Any, Protocol

import psycopg


class StatusStoreBackend(Protocol):
    def record_event(self, event: dict[str, Any]) -> None: ...
    def record_finding(self, envelope: dict[str, Any]) -> None: ...
    def record_critic(self, feedback: dict[str, Any]) -> None: ...
    def record_narrative(self, text: str) -> None: ...
    def record_awaiting_approval(self, record: dict[str, Any]) -> None: ...
    def record_escalation(self, record: dict[str, Any]) -> None: ...
    def snapshot(self) -> dict[str, Any]: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS control_status_records (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_control_status_kind_created
    ON control_status_records (kind, created_at DESC);
"""


class PostgresStatusStore:
    """Durable control-plane status feed in Postgres."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    def _insert(self, kind: str, payload: dict[str, Any]) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "INSERT INTO control_status_records (kind, payload) VALUES (%s, %s::jsonb)",
                (kind, json.dumps(payload, ensure_ascii=False)),
            )
            conn.commit()

    def _fetch_recent(self, kind: str, limit: int) -> list[dict[str, Any]]:
        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute(
                """
                SELECT payload FROM control_status_records
                WHERE kind = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (kind, limit),
            ).fetchall()
        return [row[0] for row in rows]

    def record_event(self, event: dict[str, Any]) -> None:
        self._insert("event", event)

    def record_finding(self, envelope: dict[str, Any]) -> None:
        self._insert("finding", envelope)

    def record_critic(self, feedback: dict[str, Any]) -> None:
        self._insert("critic", feedback)

    def record_narrative(self, text: str) -> None:
        self._insert("narrative", {"text": text})

    def record_awaiting_approval(self, record: dict[str, Any]) -> None:
        self._insert("awaiting_approval", record)

    def record_escalation(self, record: dict[str, Any]) -> None:
        self._insert("escalation", record)

    def snapshot(self) -> dict[str, Any]:
        events = self._fetch_recent("event", 20)
        findings = self._fetch_recent("finding", 20)
        critic_feedback = self._fetch_recent("critic", 20)
        narratives = [item.get("text", "") for item in self._fetch_recent("narrative", 10)]
        awaiting = self._fetch_recent("awaiting_approval", 20)
        escalations = self._fetch_recent("escalation", 20)
        return {
            "events_count": len(events),
            "findings_count": len(findings),
            "latest_narrative": narratives[0] if narratives else "",
            "events": events,
            "findings": findings,
            "critic_feedback": critic_feedback,
            "narratives": narratives,
            "awaiting_approval": awaiting,
            "escalations": escalations,
        }
