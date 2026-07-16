from __future__ import annotations

from typing import Any, Protocol

from cys_core.domain.engagement.models import Engagement


class EngagementStateStore(Protocol):
    def get(self, tenant_id: str, engagement_id: str) -> Engagement | None: ...

    def upsert(self, engagement: Engagement) -> None: ...

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[Engagement]: ...

    def list_recent_page(
        self,
        tenant_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Engagement], str | None]: ...

    def mark_persona_done(self, tenant_id: str, engagement_id: str, persona: str) -> None: ...

    def mark_persona_failed(self, tenant_id: str, engagement_id: str, persona: str) -> None: ...

    def append_finding(self, tenant_id: str, engagement_id: str, finding: dict[str, Any]) -> None: ...

    def set_final_report(self, tenant_id: str, engagement_id: str, report: dict[str, Any]) -> None: ...

    def mark_synthesis_running(self, tenant_id: str, engagement_id: str, job_id: str) -> None: ...

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
    ) -> None: ...

    def fail_engagement(self, tenant_id: str, engagement_id: str, *, reason: str) -> None: ...

    def fail_synthesis(self, tenant_id: str, engagement_id: str, *, reason: str) -> None: ...
