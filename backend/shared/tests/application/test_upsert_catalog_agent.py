from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.seed_catalog import SeedCatalog
from cys_core.application.use_cases.upsert_catalog_agent import UpsertCatalogAgent
from cys_core.domain.catalog.models import AgentCatalogEntry, CatalogSource, ProfilePack
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog
from tests.application.port_fakes import fake_catalog_seed_loaders, fake_schema_registry


@pytest.mark.unit
def test_upsert_catalog_agent():
    catalog = InMemoryAgentCatalog()
    saved = UpsertCatalogAgent(catalog, schema_registry=fake_schema_registry()).execute(
        "soc", {"description": "d", "role": "worker"}
    )
    assert saved.name == "soc"
    assert catalog.get_agent("soc") is not None


@pytest.mark.unit
def test_seed_catalog():
    catalog = InMemoryAgentCatalog()
    profile = ProfilePack(id="p1", name="Pack", description="d")
    entries = [
        AgentCatalogEntry(
            name="soc",
            description="",
            role="worker",
            profile_id="p1",
            source=CatalogSource.SEED,
        )
    ]

    def _load():
        return profile, entries

    tool_catalog = MagicMock()
    out = SeedCatalog(
        catalog,
        tool_catalog=tool_catalog,
        seed_loaders=fake_catalog_seed_loaders(),
        load_profile_pack=_load,
        load_tools_for_seed=lambda _profile_id: [],
    ).execute()
    assert out["seeded"] == 1
    tool_catalog.seed.assert_called_once()
