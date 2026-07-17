from __future__ import annotations

from typing import Protocol

from cys_core.domain.catalog.models import ToolCatalogEntry


class ToolCatalogPort(Protocol):
    def list_tools(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[ToolCatalogEntry]: ...

    def get_tool(self, tool_id: str, *, profile_id: str | None = None) -> ToolCatalogEntry | None: ...

    def upsert_tool(self, entry: ToolCatalogEntry) -> ToolCatalogEntry: ...

    def seed(self, entries: list[ToolCatalogEntry]) -> None: ...
