from __future__ import annotations

import pytest

from bootstrap.catalog_loader import load_profile_pack
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog


@pytest.mark.unit
def test_catalog_seed_and_upsert():
    catalog = InMemoryAgentCatalog()
    profile, entries = load_profile_pack()
    catalog.seed(entries, profile)
    assert catalog.get_agent("soc") is not None
    entry = catalog.get_agent("soc")
    assert entry is not None
    entry.description = "updated"
    catalog.upsert_agent(entry)
    assert catalog.get_agent("soc").version >= 1
