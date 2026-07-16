from __future__ import annotations

from cys_core.domain.catalog.models import SkillCatalogEntry
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.json_payload_catalog import JsonPayloadCatalog


def _merge_skill_version(new: SkillCatalogEntry, existing: SkillCatalogEntry) -> None:
    new.version = existing.version + 1
    new.quality = existing.quality


class InMemorySkillCatalog(JsonPayloadCatalog[SkillCatalogEntry]):
    def list_skills(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[SkillCatalogEntry]:
        return self.list_items(profile_id=profile_id, enabled_only=enabled_only)

    def get_skill(self, skill_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> SkillCatalogEntry | None:
        return self.get_item(skill_id, profile_id=profile_id)

    def upsert_skill(self, entry: SkillCatalogEntry) -> SkillCatalogEntry:
        return self.upsert_item(entry, merge=_merge_skill_version)

    def delete_skill(self, skill_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> bool:
        return self.soft_delete(skill_id, profile_id=profile_id)

    def increment_usage(self, skill_id: str, *, profile_id: str = DEFAULT_PROFILE_ID, error: bool = False) -> None:
        entry = self.get_skill(skill_id, profile_id=profile_id)
        if entry is None:
            return
        if error:
            entry.quality.load_errors += 1
        else:
            entry.quality.usage_count += 1
