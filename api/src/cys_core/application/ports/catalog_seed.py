from __future__ import annotations

from typing import Protocol

from cys_core.domain.catalog.models import McpServerEntry, PlanCatalogEntry, SkillCatalogEntry


class CatalogSeedLoadersPort(Protocol):
    def load_skills(self, profile_id: str) -> list[SkillCatalogEntry]: ...

    def load_plans(self, profile_id: str) -> list[PlanCatalogEntry]: ...

    def load_mcp_servers(self, profile_id: str) -> list[McpServerEntry]: ...
