from __future__ import annotations

import json

import psycopg

from cys_core.domain.runs.state_models import RunState
from cys_core.infrastructure.postgres_retry import connect_with_retry

_RUN_STATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS run_states (
    tenant_id TEXT NOT NULL DEFAULT 'default',
    context_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, context_id, kind)
);
CREATE INDEX IF NOT EXISTS idx_run_states_tenant_updated ON run_states (tenant_id, updated_at DESC);
"""


class PostgresRunStateStore:
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url
        with psycopg.connect(self._postgres_url) as conn:
            conn.execute(_RUN_STATE_SCHEMA_SQL)
            conn.commit()

    def _connect(self) -> psycopg.Connection:
        return connect_with_retry(self._postgres_url)

    def get(self, tenant_id: str, context_id: str, kind: str) -> RunState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM run_states WHERE tenant_id = %s AND context_id = %s AND kind = %s",
                (tenant_id, context_id, kind),
            ).fetchone()
        if row is None:
            return None
        return RunState.model_validate(row[0])

    def upsert(self, state: RunState) -> None:
        ctx = state.run_context
        payload = state.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_states (tenant_id, context_id, kind, payload, updated_at)
                VALUES (%s, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (tenant_id, context_id, kind) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    updated_at = NOW()
                """,
                (ctx.tenant_id, ctx.context_id, ctx.kind.value, json.dumps(payload)),
            )
            conn.commit()

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[RunState]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload FROM run_states
                WHERE tenant_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (tenant_id, limit),
            ).fetchall()
        return [RunState.model_validate(row[0]) for row in rows]
