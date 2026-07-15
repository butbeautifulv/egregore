from __future__ import annotations

from cys_core.domain.catalog.models import PlanCatalogEntry
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.json_payload_catalog import JsonPayloadCatalog


def _merge_plan_version(new: PlanCatalogEntry, existing: PlanCatalogEntry) -> None:
    new.version = existing.version + 1


class InMemoryPlanCatalog(JsonPayloadCatalog[PlanCatalogEntry]):
    def list_plans(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[PlanCatalogEntry]:
        return self.list_items(profile_id=profile_id, enabled_only=enabled_only)

    def get_plan(self, plan_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> PlanCatalogEntry | None:
        return self.get_item(plan_id, profile_id=profile_id)

    def load_active(self, profile_id: str = DEFAULT_PROFILE_ID) -> list[PlanCatalogEntry]:
        with self._lock:
            active = [
                item
                for key, item in self._items.items()
                if key[1] == profile_id and item.enabled and item.active
            ]
        if active:
            return active
        return self.list_plans(profile_id=profile_id, enabled_only=True)

    def upsert_plan(self, entry: PlanCatalogEntry) -> PlanCatalogEntry:
        return self.upsert_item(entry, merge=_merge_plan_version)

    def activate_plan(self, plan_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> PlanCatalogEntry | None:
        with self._lock:
            for key, item in self._items.items():
                if key[1] == profile_id:
                    item.active = key[0] == (plan_id, profile_id)
            return self._items.get((plan_id, profile_id))
