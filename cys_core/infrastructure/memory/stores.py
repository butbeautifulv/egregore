from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

import psycopg

from cys_core.domain.memory.models import InvestigationState, MemoryEntry, MemoryScope


class InMemoryEpisodicMemoryStore:
    """Process-local episodic memory for tests and dev fallback."""

    def __init__(self) -> None:
        self._entries: list[MemoryEntry] = []
        self._lock = threading.Lock()

    def append(self, entry: MemoryEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def query(self, scope: MemoryScope, *, limit: int = 20) -> list[MemoryEntry]:
        with self._lock:
            matches = [
                entry
                for entry in self._entries
                if entry.scope.tenant_id == scope.tenant_id
                and entry.scope.investigation_id == scope.investigation_id
                and (scope.persona is None or entry.scope.persona in (None, scope.persona))
            ]
        matches.sort(key=lambda item: item.created_at, reverse=True)
        return matches[:limit]

    def search_by_investigation(self, tenant_id: str, investigation_id: str, *, limit: int = 20) -> list[MemoryEntry]:
        return self.query(MemoryScope(tenant_id=tenant_id, investigation_id=investigation_id), limit=limit)


class InMemoryInvestigationStateStore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], InvestigationState] = {}
        self._lock = threading.Lock()

    def _key(self, tenant_id: str, investigation_id: str) -> tuple[str, str]:
        return tenant_id, investigation_id

    def get(self, tenant_id: str, investigation_id: str) -> InvestigationState | None:
        with self._lock:
            return self._states.get(self._key(tenant_id, investigation_id))

    def upsert(self, state: InvestigationState) -> None:
        with self._lock:
            self._states[self._key(state.tenant_id, state.investigation_id)] = state

    def append_finding(self, tenant_id: str, investigation_id: str, finding: dict[str, Any]) -> None:
        with self._lock:
            key = self._key(tenant_id, investigation_id)
            state = self._states.get(key)
            if state is None:
                state = InvestigationState(investigation_id=investigation_id, tenant_id=tenant_id, status="in_progress")
            state.findings_summary.append(finding)
            if state.status == "open":
                state.status = "in_progress"
            self._states[key] = state

    def mark_persona_done(self, tenant_id: str, investigation_id: str, persona: str) -> None:
        with self._lock:
            key = self._key(tenant_id, investigation_id)
            state = self._states.get(key)
            if state is None:
                state = InvestigationState(investigation_id=investigation_id, tenant_id=tenant_id, status="in_progress")
            if persona not in state.completed_personas:
                state.completed_personas.append(persona)
            self._states[key] = state

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[InvestigationState]:
        with self._lock:
            states = [state for state in self._states.values() if state.tenant_id == tenant_id]
        return states[:limit]


_MEMORY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_memory_entries (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    investigation_id TEXT NOT NULL,
    persona TEXT,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    source_agent TEXT NOT NULL DEFAULT '',
    source_job_id TEXT NOT NULL DEFAULT '',
    trust_score DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    checksum TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_memory_investigation
    ON agent_memory_entries (tenant_id, investigation_id, created_at DESC);

CREATE TABLE IF NOT EXISTS investigation_states (
    tenant_id TEXT NOT NULL,
    investigation_id TEXT NOT NULL,
    state_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, investigation_id)
);
"""


class PostgresEpisodicMemoryStore:
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url
        self._ensure_schema()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._postgres_url)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_MEMORY_SCHEMA_SQL)
            conn.commit()

    def append(self, entry: MemoryEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_memory_entries (
                    id, tenant_id, investigation_id, persona, content, memory_type,
                    source_agent, source_job_id, trust_score, checksum, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    entry.id,
                    entry.scope.tenant_id,
                    entry.scope.investigation_id,
                    entry.scope.persona,
                    entry.content,
                    entry.memory_type,
                    entry.source_agent,
                    entry.source_job_id,
                    entry.trust_score,
                    entry.checksum,
                    entry.created_at,
                ),
            )
            conn.commit()

    def query(self, scope: MemoryScope, *, limit: int = 20) -> list[MemoryEntry]:
        with self._connect() as conn:
            if scope.persona is None:
                rows = conn.execute(
                    """
                    SELECT id, tenant_id, investigation_id, persona, content, memory_type,
                           source_agent, source_job_id, trust_score, checksum, created_at
                    FROM agent_memory_entries
                    WHERE tenant_id = %s AND investigation_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (scope.tenant_id, scope.investigation_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, tenant_id, investigation_id, persona, content, memory_type,
                           source_agent, source_job_id, trust_score, checksum, created_at
                    FROM agent_memory_entries
                    WHERE tenant_id = %s AND investigation_id = %s
                      AND (persona IS NULL OR persona = %s)
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (scope.tenant_id, scope.investigation_id, scope.persona, limit),
                ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def search_by_investigation(self, tenant_id: str, investigation_id: str, *, limit: int = 20) -> list[MemoryEntry]:
        return self.query(MemoryScope(tenant_id=tenant_id, investigation_id=investigation_id), limit=limit)

    @staticmethod
    def _row_to_entry(row: tuple[Any, ...]) -> MemoryEntry:
        created_at = row[10]
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return MemoryEntry(
            id=row[0],
            scope=MemoryScope(tenant_id=row[1], investigation_id=row[2], persona=row[3]),
            content=row[4],
            memory_type=row[5],
            source_agent=row[6],
            source_job_id=row[7],
            trust_score=float(row[8]),
            checksum=row[9],
            created_at=created_at,
        )


class PostgresInvestigationStateStore:
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url
        self._ensure_schema()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._postgres_url)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_MEMORY_SCHEMA_SQL)
            conn.commit()

    def get(self, tenant_id: str, investigation_id: str) -> InvestigationState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM investigation_states WHERE tenant_id = %s AND investigation_id = %s",
                (tenant_id, investigation_id),
            ).fetchone()
        if row is None:
            return None
        return InvestigationState.model_validate(row[0])

    def upsert(self, state: InvestigationState) -> None:
        payload = state.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO investigation_states (tenant_id, investigation_id, state_json, updated_at)
                VALUES (%s, %s, %s::jsonb, NOW())
                ON CONFLICT (tenant_id, investigation_id)
                DO UPDATE SET state_json = EXCLUDED.state_json, updated_at = NOW()
                """,
                (state.tenant_id, state.investigation_id, json.dumps(payload)),
            )
            conn.commit()

    def append_finding(self, tenant_id: str, investigation_id: str, finding: dict[str, Any]) -> None:
        state = self.get(tenant_id, investigation_id)
        if state is None:
            state = InvestigationState(investigation_id=investigation_id, tenant_id=tenant_id, status="in_progress")
        state.findings_summary.append(finding)
        if state.status == "open":
            state.status = "in_progress"
        self.upsert(state)

    def mark_persona_done(self, tenant_id: str, investigation_id: str, persona: str) -> None:
        state = self.get(tenant_id, investigation_id)
        if state is None:
            state = InvestigationState(investigation_id=investigation_id, tenant_id=tenant_id, status="in_progress")
        if persona not in state.completed_personas:
            state.completed_personas.append(persona)
        self.upsert(state)

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[InvestigationState]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT state_json FROM investigation_states
                WHERE tenant_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (tenant_id, limit),
            ).fetchall()
        return [InvestigationState.model_validate(row[0]) for row in rows]
