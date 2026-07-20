from __future__ import annotations

from cys_core.domain.catalog.models import McpServerEntry
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.json_payload_catalog import JsonPayloadCatalog


class InMemoryMcpServerCatalog(JsonPayloadCatalog[McpServerEntry]):
    def list_servers(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[McpServerEntry]:
        return self.list_items(profile_id=profile_id, enabled_only=enabled_only)

    def get_server(self, server_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> McpServerEntry | None:
        return self.get_item(server_id, profile_id=profile_id)

    def upsert_server(self, entry: McpServerEntry) -> McpServerEntry:
        return self.upsert_item(entry)
