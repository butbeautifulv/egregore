from __future__ import annotations

from collections.abc import Callable

from cys_core.application.routing.event_router import EventRouter
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.events.models import RoutingDecision, SecurityEvent


class RouteEvent:
    """Route a security event and record plan-quality side effects.

    Plan-quality recording (cys_core.application.use_cases.update_plan_quality.
    UpdatePlanQuality) is api-only bookkeeping — worker's routing path never
    needs it. Rather than reaching for that api-only module directly (it
    doesn't exist in worker), the caller injects an optional
    record_plan_match hook; api's container wires a real one, worker's
    passes none.
    """

    def __init__(
        self,
        router: EventRouter,
        *,
        record_event_ingested=None,
        record_plan_match: Callable[[str, int, int], None] | None = None,
    ) -> None:
        self._router = router
        self._record_event_ingested = record_event_ingested
        self._record_plan_match_hook = record_plan_match

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
        if self._record_plan_match_hook is not None:
            try:
                self._record_plan_match_hook(plan_id, rule_idx, jobs)
            except Exception:
                pass
        if self._record_event_ingested is not None:
            try:
                self._record_event_ingested(f"plan_match:{plan_id}:{rule_idx}")
            except Exception:
                pass
