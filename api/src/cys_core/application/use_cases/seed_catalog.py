from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cys_core.application.catalog_mutation_service import CatalogMutationService
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.catalog_seed import CatalogSeedLoadersPort
from cys_core.application.ports.tool_catalog import ToolCatalogPort
from cys_core.domain.catalog.models import ProfilePack


class SeedCatalog:
    def __init__(
        self,
        catalog: AgentCatalogPort,
        *,
        tool_catalog: ToolCatalogPort,
        seed_loaders: CatalogSeedLoadersPort,
        load_profile_pack: Callable[[], tuple[ProfilePack, list]],
        load_tools_for_seed: Callable[[str], list[Any]],
        reload: Callable[[], None] | None = None,
        mutation: CatalogMutationService | None = None,
    ) -> None:
        self.catalog = catalog
        self.tool_catalog = tool_catalog
        self._seed_loaders = seed_loaders
        self.load_profile_pack = load_profile_pack
        self.load_tools_for_seed = load_tools_for_seed
        self.reload = reload or (lambda: None)
        self._mutation = mutation

    def execute(self) -> dict:
        profile, entries = self.load_profile_pack()
        skills = self._seed_loaders.load_skills(profile.id)
        plans = self._seed_loaders.load_plans(profile.id)
        mcp_servers = self._seed_loaders.load_mcp_servers(profile.id)
        tools = self.load_tools_for_seed(profile.id)
        counts = self._mutation.seed_pack(
            profile,
            entries,
            skills=skills,
            plans=plans,
            mcp_servers=mcp_servers,
            tools=tools,
        ) if self._mutation is not None else self._legacy_seed(
            profile, entries, skills=skills, plans=plans, mcp_servers=mcp_servers, tools=tools
        )
        return {
            "profile": profile.model_dump(),
            **counts,
        }

    def _legacy_seed(self, profile, entries, *, skills, plans, mcp_servers, tools):
        self.catalog.seed(entries, profile, skills=skills, plans=plans, mcp_servers=mcp_servers)
        self.tool_catalog.seed(tools)
        self.reload()
        return {
            "seeded": len(entries),
            "skills": len(skills),
            "plans": len(plans),
            "mcp_servers": len(mcp_servers),
            "tools": len(tools),
        }
