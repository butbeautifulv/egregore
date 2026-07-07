from __future__ import annotations

import json
from typing import Any

import psycopg

from cys_core.domain.engagement.models import Engagement, EngagementStatus, ExecutionMode, SynthesisStatus

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
        items.reverse()
        return items

    def mark_persona_done(self, tenant_id: str, engagement_id: str, persona: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        engagement.record_persona_completed(persona)
        self.upsert(engagement)

    def mark_persona_failed(self, tenant_id: str, engagement_id: str, persona: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        engagement.record_persona_failed(persona)
        self.upsert(engagement)

    def append_finding(self, tenant_id: str, engagement_id: str, finding: dict[str, Any]) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        engagement.findings_summary.append(finding)
        self.upsert(engagement)

    def set_final_report(self, tenant_id: str, engagement_id: str, report: dict[str, Any]) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        engagement.complete_synthesis(report)
        self.upsert(engagement)

    def mark_synthesis_running(self, tenant_id: str, engagement_id: str, job_id: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        engagement.synthesis_status = SynthesisStatus.RUNNING
        if job_id not in engagement.job_ids:
            engagement.job_ids.append(job_id)
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
    ) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        mode = ExecutionMode(execution_mode) if execution_mode else None
        if planner_plan is not None:
            engagement.apply_planner_result(
                planner_plan,
                status=planner_status or engagement.planner_status or "planning",
                rationale=planner_rationale,
                error=planner_error,
                goal=goal,
                execution_mode=mode,
                synthesis_persona=synthesis_persona,
            )
        else:
            if planner_status is not None:
                engagement.planner_status = planner_status
            if planner_rationale:
                engagement.planner_rationale = planner_rationale
            if planner_error:
                engagement.planner_error = planner_error
            if goal is not None:
                engagement.goal = goal
            if execution_mode is not None:
                engagement.execution_mode = mode
            if synthesis_persona is not None:
                engagement.synthesis_persona = synthesis_persona
            if engagement.status == EngagementStatus.CREATED:
                engagement.begin_planning(goal=goal)
        self.upsert(engagement)

    def fail_engagement(self, tenant_id: str, engagement_id: str, *, reason: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        engagement.fail_guardrail(reason)
        self.upsert(engagement)

    def fail_synthesis(self, tenant_id: str, engagement_id: str, *, reason: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        engagement.fail_synthesis(reason)
        self.upsert(engagement)
