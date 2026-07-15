from __future__ import annotations

import threading

from cys_core.domain.catalog.models import AgentCatalogEntry, CatalogSource, CatalogVersion, ProfilePack


class InMemoryAgentCatalog:
    def __init__(self) -> None:
        self._agents: dict[str, AgentCatalogEntry] = {}
        self._profiles: dict[str, ProfilePack] = {}
        self._versions: dict[str, int] = {}
        self._lock = threading.Lock()

    def list_agents(self, *, profile_id: str | None = None, enabled_only: bool = True) -> list[AgentCatalogEntry]:
        with self._lock:
            items = list(self._agents.values())
        if profile_id:
            items = [item for item in items if item.profile_id == profile_id]
        if enabled_only:
            items = [item for item in items if item.enabled]
        return sorted(items, key=lambda item: item.name)

    def get_agent(self, name: str) -> AgentCatalogEntry | None:
        with self._lock:
            return self._agents.get(name)

    def upsert_agent(self, entry: AgentCatalogEntry) -> AgentCatalogEntry:
        with self._lock:
            existing = self._agents.get(entry.name)
            if existing is not None:
                entry.version = existing.version + 1
                entry.quality = existing.quality
            entry.source = CatalogSource.API
            self._agents[entry.name] = entry
            self._versions[entry.profile_id] = self._versions.get(entry.profile_id, 0) + 1
            return entry

    def delete_agent(self, name: str, *, profile_id: str = "cybersec-soc") -> bool:
        with self._lock:
            entry = self._agents.get(name)
            if entry is None or entry.profile_id != profile_id:
                return False
            entry.enabled = False
            return True

    def upsert_profile(self, profile: ProfilePack) -> ProfilePack:
        with self._lock:
            self._profiles[profile.id] = profile
            return profile

    def list_profiles(self) -> list[ProfilePack]:
        with self._lock:
            return list(self._profiles.values())

    def get_version(self, profile_id: str) -> CatalogVersion:
        with self._lock:
            count = sum(1 for agent in self._agents.values() if agent.profile_id == profile_id and agent.enabled)
            return CatalogVersion(
                profile_id=profile_id,
                version=self._versions.get(profile_id, 0),
                agent_count=count,
            )

    def seed(
        self,
        entries: list[AgentCatalogEntry],
        profile: ProfilePack,
        *,
        skills=None,
        plans=None,
        mcp_servers=None,
    ) -> None:
        with self._lock:
            self._profiles[profile.id] = profile
            for entry in entries:
                self._agents[entry.name] = entry
        from cys_core.infrastructure.catalog.catalog_seed_writer import fan_out_secondary_catalogs

        fan_out_secondary_catalogs(skills=skills, plans=plans, mcp_servers=mcp_servers)
