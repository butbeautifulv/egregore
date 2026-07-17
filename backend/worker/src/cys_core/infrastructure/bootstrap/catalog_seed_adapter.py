from __future__ import annotations

from bootstrap import catalog_seed_loaders as _loaders
from cys_core.application.ports.catalog_seed import CatalogSeedLoadersPort


class BootstrapCatalogSeedLoadersAdapter:
    def load_skills(self, profile_id: str):
        return _loaders.load_skills_for_seed(profile_id)

    def load_plans(self, profile_id: str):
        return _loaders.load_plans_for_seed(profile_id)

    def load_mcp_servers(self, profile_id: str):
        return _loaders.load_mcp_servers_for_seed(profile_id)


def build_catalog_seed_loaders_port() -> CatalogSeedLoadersPort:
    return BootstrapCatalogSeedLoadersAdapter()
