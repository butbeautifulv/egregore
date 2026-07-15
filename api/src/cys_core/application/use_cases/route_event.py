from __future__ import annotations

from cys_core.application.routing.event_router import EventRouter
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.events.models import RoutingDecision, SecurityEvent


class RouteEvent:
    """Route a security event and record plan-quality side effects."""

    def __init__(
        self,
        router: EventRouter,
        *,
        plan_catalog=None,
        record_event_ingested=None,
        mutation=None,
    ) -> None:
        self._router = router
        self._plan_catalog = plan_catalog
        self._record_event_ingested = record_event_ingested
        self._mutation = mutation

    def execute(self, event: SecurityEvent, *, profile_id: str = DEFAULT_PROFILE_ID) -> RoutingDecision:
        decision = self._router.route(event, profile_id=profile_id)
        if decision.matched_plan_id:
            self._record_plan_match(
                decision.matched_plan_id,
                decision.matched_rule_idx,
                len(decision.personas),
            )
        return decision

    def _record_plan_match(self, plan_id: str, rule_idx: int, jobs: int) -> None:
        if self._plan_catalog is not None:
            try:
                from cys_core.application.use_cases.update_plan_quality import UpdatePlanQuality

                UpdatePlanQuality(self._plan_catalog, mutation=self._mutation).record_match(plan_id, jobs=jobs)
            except Exception:
                pass
        if self._record_event_ingested is not None:
            try:
                self._record_event_ingested(f"plan_match:{plan_id}:{rule_idx}")
            except Exception:
                pass
