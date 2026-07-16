from __future__ import annotations

from cys_core.domain.catalog.models import CatalogSource, ToolCatalogEntry
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.json_payload_catalog import JsonPayloadCatalog


class InMemoryToolCatalog(JsonPayloadCatalog[ToolCatalogEntry]):
    def __init__(self) -> None:
        super().__init__(sort_key=lambda item: item.name)

    def list_tools(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[ToolCatalogEntry]:
        return self.list_items(profile_id=profile_id, enabled_only=enabled_only)

    def get_tool(self, tool_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> ToolCatalogEntry | None:
        return self.get_item(tool_id, profile_id=profile_id)

    def upsert_tool(self, entry: ToolCatalogEntry) -> ToolCatalogEntry:
        entry.source = CatalogSource.API
        return self.upsert_item(entry)

    def seed(self, entries: list[ToolCatalogEntry]) -> None:
        self.seed_items(entries)
