from __future__ import annotations

from typing import Any

from cys_core.domain.engagement.models import Engagement
from cys_core.infrastructure.engagement import _store_ops


class MemoryEngagementStateStore:
    def __init__(self) -> None:
        from collections import defaultdict

        self._by_tenant: dict[str, dict[str, Engagement]] = defaultdict(dict)

    def get(self, tenant_id: str, engagement_id: str) -> Engagement | None:
        return self._by_tenant.get(tenant_id, {}).get(engagement_id)

    def upsert(self, engagement: Engagement) -> None:
        self._by_tenant[engagement.tenant_id][engagement.id] = engagement

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[Engagement]:
        items = list(self._by_tenant.get(tenant_id, {}).values())
        return list(reversed(items))[:limit]

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
