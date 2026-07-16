from __future__ import annotations

from cys_core.application.catalog_mutation_service import CatalogMutationService
from cys_core.application.ports.registry_catalogs import PlanCatalogPort


class UpdatePlanQuality:
    def __init__(
        self,
        plan_catalog: PlanCatalogPort,
        *,
        mutation: CatalogMutationService | None = None,
    ) -> None:
        self._plans = plan_catalog
        self._mutation = mutation

    def record_match(self, plan_id: str, *, profile_id: str = "cybersec-soc", jobs: int = 1) -> None:
        entry = self._plans.get_plan(plan_id, profile_id=profile_id)
        if entry is None:
            return
        entry.quality.match_count += 1
        entry.quality.avg_jobs_per_event = (
            (entry.quality.avg_jobs_per_event * max(0, entry.quality.match_count - 1) + jobs)
            / max(1, entry.quality.match_count)
        )
        if self._mutation is not None:
            self._mutation.upsert_plan(entry, actor="quality")
        else:
            self._plans.upsert_plan(entry)
