from __future__ import annotations

from typing import Protocol

from cys_core.domain.catalog.models import (
    AgentCatalogEntry,
    McpServerEntry,
    PlanCatalogEntry,
    ProfilePack,
    SkillCatalogEntry,
)


class SkillCatalogPort(Protocol):
    def list_skills(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[SkillCatalogEntry]: ...

    def get_skill(self, skill_id: str, *, profile_id: str = "cybersec-soc") -> SkillCatalogEntry | None: ...

    def upsert_skill(self, entry: SkillCatalogEntry) -> SkillCatalogEntry: ...

    def delete_skill(self, skill_id: str, *, profile_id: str = "cybersec-soc") -> bool: ...


class PlanCatalogPort(Protocol):
    def list_plans(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[PlanCatalogEntry]: ...

    def get_plan(self, plan_id: str, *, profile_id: str = "cybersec-soc") -> PlanCatalogEntry | None: ...

    def load_active(self, profile_id: str = "cybersec-soc") -> list[PlanCatalogEntry]: ...

    def upsert_plan(self, entry: PlanCatalogEntry) -> PlanCatalogEntry: ...

    def activate_plan(self, plan_id: str, *, profile_id: str = "cybersec-soc") -> PlanCatalogEntry | None: ...


class McpServerCatalogPort(Protocol):
    def list_servers(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[McpServerEntry]: ...

    def get_server(self, server_id: str, *, profile_id: str = "cybersec-soc") -> McpServerEntry | None: ...

    def upsert_server(self, entry: McpServerEntry) -> McpServerEntry: ...


class CatalogRegistryPort(Protocol):
    def list_agents(self, *, profile_id: str | None = None, enabled_only: bool = True) -> list[AgentCatalogEntry]: ...

    def get_agent(self, name: str) -> AgentCatalogEntry | None: ...

    def upsert_agent(self, entry: AgentCatalogEntry) -> AgentCatalogEntry: ...

    def delete_agent(self, name: str, *, profile_id: str = "cybersec-soc") -> bool: ...

    def list_profiles(self) -> list[ProfilePack]: ...

    def upsert_profile(self, profile: ProfilePack) -> ProfilePack: ...

    def seed(
        self,
        entries: list[AgentCatalogEntry],
        profile: ProfilePack,
        *,
        skills: list[SkillCatalogEntry] | None = None,
        plans: list[PlanCatalogEntry] | None = None,
        mcp_servers: list[McpServerEntry] | None = None,
    ) -> None: ...
