from __future__ import annotations

from collections import defaultdict
from typing import Any

from cys_core.domain.engagement.models import Engagement, EngagementStatus


class MemoryEngagementStateStore:
    def __init__(self) -> None:
        self._by_tenant: dict[str, dict[str, Engagement]] = defaultdict(dict)

    def get(self, tenant_id: str, engagement_id: str) -> Engagement | None:
        return self._by_tenant.get(tenant_id, {}).get(engagement_id)

    def upsert(self, engagement: Engagement) -> None:
        self._by_tenant[engagement.tenant_id][engagement.id] = engagement

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[Engagement]:
        items = list(self._by_tenant.get(tenant_id, {}).values())
        return items[-limit:]

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
    ) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        if planner_plan is not None:
            engagement.apply_planner_result(
                planner_plan,
                status=planner_status or engagement.planner_status or "planning",
                rationale=planner_rationale,
                error=planner_error,
                goal=goal,
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
            if engagement.status == EngagementStatus.CREATED:
                engagement.begin_planning(goal=goal)
        self.upsert(engagement)

    def fail_engagement(self, tenant_id: str, engagement_id: str, *, reason: str) -> None:
        engagement = self.get(tenant_id, engagement_id)
        if engagement is None:
            return
        engagement.fail_guardrail(reason)
        self.upsert(engagement)
