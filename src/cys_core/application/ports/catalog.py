from __future__ import annotations

from typing import Protocol

from cys_core.domain.catalog.models import AgentCatalogEntry, CatalogVersion, ProfilePack

# AgentCatalogPort covers agent entries and profile packs (write-path seeding).
# Resource catalogs (skills, plans, MCP servers, tools) use separate ports in
# application/ports/registry_catalogs.py and application/ports/tool_catalog.py.
# There is no CatalogRegistryPort — catalog_registry implements AgentCatalogPort only.


class AgentCatalogPort(Protocol):
    def list_agents(self, *, profile_id: str | None = None, enabled_only: bool = True) -> list[AgentCatalogEntry]: ...

    def get_agent(self, name: str) -> AgentCatalogEntry | None: ...

    def upsert_agent(self, entry: AgentCatalogEntry) -> AgentCatalogEntry: ...

    def delete_agent(self, name: str, *, profile_id: str = "cybersec-soc") -> bool: ...

    def list_profiles(self) -> list[ProfilePack]: ...

    def upsert_profile(self, profile: ProfilePack) -> ProfilePack: ...

    def get_version(self, profile_id: str) -> CatalogVersion: ...

    def seed(self, entries: list[AgentCatalogEntry], profile: ProfilePack, **kwargs) -> None: ...
