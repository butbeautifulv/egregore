"""Meta-level LLM planner for engagements (profile-driven)."""

from __future__ import annotations

from typing import Any

from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.persona_ranking import PersonaRankingPort
from cys_core.application.ports.resource_source import ResourceSourcePort
from cys_core.application.ports.tracing_ports import NOOP_APPLICATION_TRACING, ApplicationTracingPort
from cys_core.application.use_cases.plan_investigation import PlanInvestigation, PlannerRuntime
from cys_core.domain.engagement.models import EngagementPlan
from cys_core.domain.events.models import SecurityEvent


class MetaPlanner:
    """Profile-aware wrapper over PlanInvestigation."""

    def __init__(
        self,
        *,
        runtime: PlannerRuntime,
        engagement_store,
        resource_source: ResourceSourcePort,
        persona_ranking: PersonaRankingPort,
        agent_catalog: AgentCatalogPort,
        planner_persona: str = "planner",
        profile_id: str = "cybersec-soc",
        application_tracing: ApplicationTracingPort | None = None,
    ) -> None:
        tracing = application_tracing or NOOP_APPLICATION_TRACING
        self._inner = PlanInvestigation(
            runtime=runtime,
            engagement_store=engagement_store,
            resource_source=resource_source,
            persona_ranking=persona_ranking,
            agent_catalog=agent_catalog,
            planner_persona=planner_persona,
            profile_id=profile_id,
            application_tracing=tracing,
        )

    @property
    def profile_id(self) -> str:
        return self._inner.profile_id

    def begin_planning(self, event: SecurityEvent):
        return self._inner.begin_planning(event)

    async def execute(self, event: SecurityEvent, *, profile_id: str | None = None) -> EngagementPlan:
        if profile_id:
            self._inner.profile_id = profile_id
        return await self._inner.execute(event)

    def to_worker_jobs_payload(self, plan: EngagementPlan) -> dict[str, Any]:
        return self._inner.to_worker_jobs_payload(plan)


__all__ = ["EngagementPlan", "MetaPlanner", "PlannerRuntime"]
