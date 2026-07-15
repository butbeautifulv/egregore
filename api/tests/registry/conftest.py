from __future__ import annotations

import pytest

from bootstrap.catalog_loader import load_profile_pack
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog
from tests.conftest import patch_catalog


@pytest.fixture(autouse=True)
def _full_agent_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    profile, entries = load_profile_pack()
    catalog = InMemoryAgentCatalog()
    catalog.seed(entries, profile)
    patch_catalog(monkeypatch, catalog)
