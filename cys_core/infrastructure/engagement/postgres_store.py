from __future__ import annotations

import json
from typing import Any

import psycopg

from cys_core.domain.engagement.models import Engagement
from cys_core.infrastructure.engagement import _store_ops

_ENGAGEMENT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS engagements (
    tenant_id TEXT NOT NULL,
    engagement_id TEXT NOT NULL,
    state_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, engagement_id)
);
CREATE INDEX IF NOT EXISTS idx_engagements_updated ON engagements (tenant_id, updated_at DESC);
"""


class PostgresEngagementStateStore:
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url
        self._ensure_schema()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._postgres_url)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_ENGAGEMENT_SCHEMA_SQL)
            conn.commit()

    def _load(self, tenant_id: str, engagement_id: str) -> Engagement | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT state_json FROM engagements
                WHERE tenant_id = %s AND engagement_id = %s
                """,
                (tenant_id, engagement_id),
            ).fetchone()
        if row is None:
            return None
        return Engagement.model_validate(row[0])

    def get(self, tenant_id: str, engagement_id: str) -> Engagement | None:
        return self._load(tenant_id, engagement_id)

    def upsert(self, engagement: Engagement) -> None:
        payload = engagement.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO engagements (tenant_id, engagement_id, state_json, updated_at)
                VALUES (%s, %s, %s::jsonb, NOW())
                ON CONFLICT (tenant_id, engagement_id) DO UPDATE
                SET state_json = EXCLUDED.state_json,
                    updated_at = NOW()
                """,
                (engagement.tenant_id, engagement.id, json.dumps(payload)),
            )
            conn.commit()

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[Engagement]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT state_json FROM engagements
                WHERE tenant_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (tenant_id, limit),
            ).fetchall()
        items = [Engagement.model_validate(row[0]) for row in rows]
        return items

    def list_recent_with_updated_at(
        self, tenant_id: str, *, limit: int = 20
    ) -> list[tuple[Engagement, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT state_json, updated_at FROM engagements
                WHERE tenant_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (tenant_id, limit),
            ).fetchall()
        return [(Engagement.model_validate(row[0]), row[1]) for row in rows]

    def mark_persona_done(self, tenant_id: str, engagement_id: str, persona: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        _store_ops.mark_persona_done(engagement, persona)
        self.upsert(engagement)

    def mark_persona_failed(self, tenant_id: str, engagement_id: str, persona: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        _store_ops.mark_persona_failed(engagement, persona)
        self.upsert(engagement)

    def append_finding(self, tenant_id: str, engagement_id: str, finding: dict[str, Any]) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        _store_ops.append_finding(engagement, finding)
        self.upsert(engagement)

    def set_final_report(self, tenant_id: str, engagement_id: str, report: dict[str, Any]) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        _store_ops.set_final_report(engagement, report)
        self.upsert(engagement)

    def mark_synthesis_running(self, tenant_id: str, engagement_id: str, job_id: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        _store_ops.mark_synthesis_running(engagement, job_id)
        self.upsert(engagement)

    def update_planner_state(
        self,
        tenant_id: str,
        engagement_id: str,
        *,
        planner_plan: list[str] | None = None,
        planner_status: str | None = None,
        planner_rationale: str = "",
        planner_error: str = "",
        goal: str | None = None,
        execution_mode: str | None = None,
        synthesis_persona: str | None = None,
        planner_sub_goals: dict[str, str] | None = None,
        planner_depends_on: dict[str, list[str]] | None = None,
    ) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        _store_ops.update_planner_state(
            engagement,
            planner_plan=planner_plan,
            planner_status=planner_status,
            planner_rationale=planner_rationale,
            planner_error=planner_error,
            goal=goal,
            execution_mode=execution_mode,
            synthesis_persona=synthesis_persona,
            planner_sub_goals=planner_sub_goals,
            planner_depends_on=planner_depends_on,
        )
        self.upsert(engagement)

    def fail_engagement(self, tenant_id: str, engagement_id: str, *, reason: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        _store_ops.fail_engagement(engagement, reason=reason)
        self.upsert(engagement)

    def fail_synthesis(self, tenant_id: str, engagement_id: str, *, reason: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        _store_ops.fail_synthesis(engagement, reason=reason)
        self.upsert(engagement)
