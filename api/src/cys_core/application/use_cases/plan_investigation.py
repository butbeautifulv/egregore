from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cys_core.application.planning.catalog_planner_strategy import CatalogPlannerStrategy
from cys_core.application.planning.runtime import PlannerRuntime
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.persona_ranking import PersonaRankingPort
from cys_core.application.ports.resource_source import ResourceSourcePort
from cys_core.application.ports.tracing_ports import NOOP_APPLICATION_TRACING, ApplicationTracingPort
from cys_core.domain.engagement.models import Engagement, EngagementPlan, EngagementStatus
from cys_core.domain.events.models import SecurityEvent


class PlanInvestigation:
    """Thin delegate over catalog-driven planner strategy."""

    def __init__(
        self,
        *,
        runtime: PlannerRuntime,
        engagement_store: EngagementStateStore,
        resource_source: ResourceSourcePort,
        persona_ranking: PersonaRankingPort,
        agent_catalog: AgentCatalogPort,
        planner_persona: str = "planner",
        profile_id: str = "cybersec-soc",
        application_tracing: ApplicationTracingPort | None = None,
        engagement_egress: EngagementEgressPort | None = None,
        reload_personas: Callable[[], None] | None = None,
    ) -> None:
        self._strategy = CatalogPlannerStrategy(
            runtime=runtime,
            engagement_store=engagement_store,
            resource_source=resource_source,
            persona_ranking=persona_ranking,
            agent_catalog=agent_catalog,
            planner_persona=planner_persona,
            profile_id=profile_id,
            application_tracing=application_tracing or NOOP_APPLICATION_TRACING,
            engagement_egress=engagement_egress,
            reload_personas=reload_personas,
        )
        self.runtime = runtime
        self.engagement_store = engagement_store
        self.resource_source = resource_source
        self.persona_ranking = persona_ranking
        self.agent_catalog = agent_catalog
        self.planner_persona = planner_persona
        self.profile_id = profile_id
        self._engagement_egress = engagement_egress

    def _available_personas(self) -> list[str]:
        return self._strategy._available_personas()

    def _goal_from_event(self, event: SecurityEvent) -> str:
        return str(event.payload.get("goal", event.payload.get("message", "Investigate security incident")))

    def _engagement_id(self, event: SecurityEvent) -> str:
        return event.correlation_id or event.id

    def begin_planning(self, event: SecurityEvent) -> Engagement:
        goal = self._goal_from_event(event)
        engagement_id = self._engagement_id(event)
        engagement = self.engagement_store.get(event.tenant_id, engagement_id)
        if engagement is None:
            engagement = Engagement(
                id=engagement_id,
                tenant_id=event.tenant_id,
                goal=goal,
                status=EngagementStatus.PLANNING,
                correlation_id=engagement_id,
            )
        engagement.begin_planning(goal=goal)
        self.engagement_store.upsert(engagement)
        return engagement

    async def execute(self, event: SecurityEvent) -> EngagementPlan:
        return await self._strategy.execute(event)

    def to_worker_jobs_payload(self, plan: EngagementPlan) -> dict[str, Any]:
        mode = plan.effective_execution_mode()
        return {
            "planner_plan": plan.personas,
            "sub_goals": plan.sub_goals,
            "rationale": plan.rationale,
            "depends_on": plan.depends_on,
            "execution_mode": mode.value,
            "synthesis_persona": plan.synthesis_persona,
            "phase": "specialist",
        }


__all__ = ["PlanInvestigation", "PlannerRuntime"]
