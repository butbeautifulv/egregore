from __future__ import annotations

import pytest

from bootstrap.catalog_loader import load_profile_pack
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog
from tests.conftest import patch_catalog


@pytest.fixture(autouse=True)
def _full_agent_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc

    profile, entries = load_profile_pack()
    catalog = InMemoryAgentCatalog()
    catalog.seed(entries, profile)
    patch_catalog(monkeypatch, catalog)
    monkeypatch.setattr(rc, "_veil_mcp_enabled", False)
    monkeypatch.setattr(
        "cys_core.integrations.veil_mcp_client._ensure_veil_runtime_config",
        lambda: None,
    )
