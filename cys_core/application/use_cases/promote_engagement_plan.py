from __future__ import annotations

from cys_core.application.catalog_mutation_service import CatalogMutationService
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.domain.catalog.models import PlanCatalogEntry, CatalogSource


class PromoteEngagementPlanError(Exception):
    pass


class PromoteEngagementPlanToCatalog:
    def __init__(
        self,
        engagement_store: EngagementStateStore,
        mutation: CatalogMutationService,
        *,
        activate_plan: callable | None = None,
    ) -> None:
        self._engagement_store = engagement_store
        self._mutation = mutation
        self._activate_plan = activate_plan

    def execute(
        self,
        *,
        tenant_id: str,
        engagement_id: str,
        plan_id: str,
        activate: bool = False,
        actor: str = "api",
    ) -> PlanCatalogEntry:
        engagement = self._engagement_store.get(tenant_id, engagement_id)
        if engagement is None:
            raise PromoteEngagementPlanError("Engagement not found")
        planner_plan = engagement.planner_plan or []
        if not planner_plan:
            raise PromoteEngagementPlanError("Engagement has no planner_plan to promote")

        rationale = (engagement.planner_rationale or "").strip()
        goal = (engagement.goal or "").strip()
        entry = PlanCatalogEntry(
            id=plan_id,
            name=goal[:80] if goal else plan_id,
            description=rationale[:500] if rationale else f"Promoted from engagement {engagement_id}",
            rules=[
                {
                    "event_types": ["manual.investigation", "engagement.start"],
                    "personas": list(planner_plan),
                    "description": rationale[:500],
                }
            ],
            profile_id=engagement.profile_id or "cybersec-soc",
            enabled=True,
            active=False,
            source=CatalogSource.API,
        )
        saved = self._mutation.upsert_plan(entry, actor=actor)
        if activate and self._activate_plan is not None:
            activated = self._activate_plan(plan_id, profile_id=saved.profile_id)
            if activated is not None:
                return activated
        return saved
