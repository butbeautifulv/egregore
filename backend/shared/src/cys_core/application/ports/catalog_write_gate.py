from __future__ import annotations

from typing import Protocol

from cys_core.domain.catalog.models import (
    AgentCatalogEntry,
    McpServerEntry,
    PlanCatalogEntry,
    SkillCatalogEntry,
)


class CatalogWriteGatePort(Protocol):
    def upsert_agent(
        self, entry: AgentCatalogEntry, *, actor: str = "api"
    ) -> AgentCatalogEntry: ...

    def upsert_skill(
        self, entry: SkillCatalogEntry, *, actor: str = "api"
    ) -> SkillCatalogEntry: ...

    def upsert_plan(self, entry: PlanCatalogEntry, *, actor: str = "api") -> PlanCatalogEntry: ...

    def upsert_mcp_server(self, entry: McpServerEntry, *, actor: str = "api") -> McpServerEntry: ...

    def approve_skill(
        self, skill_id: str, *, profile_id: str = "cybersec-soc", actor: str = "api"
    ) -> SkillCatalogEntry: ...

    def delete_agent(
        self, name: str, *, profile_id: str = "cybersec-soc", actor: str = "api"
    ) -> bool: ...

    def delete_skill(
        self, skill_id: str, *, profile_id: str = "cybersec-soc", actor: str = "api"
    ) -> bool: ...
