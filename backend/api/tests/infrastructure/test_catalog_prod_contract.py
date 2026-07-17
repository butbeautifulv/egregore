from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.catalog.models import AgentCatalogEntry


@pytest.mark.unit
def test_prod_catalog_path_reads_db_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dynamic catalog must load agents from Postgres catalog only."""
    from cys_core.infrastructure.catalog import catalog_registry

    catalog = MagicMock()
    catalog.list_agents.return_value = [
        AgentCatalogEntry(
            name="consultant",
            role="worker",
            trust_level="internal",
            profile_id="cybersec-soc",
            enabled=True,
        )
    ]
    catalog.get_version.return_value = MagicMock(version=1)
    catalog.list_profiles.return_value = []

    monkeypatch.setattr(catalog_registry, "get_agent_catalog", lambda: catalog)

    with patch("cys_core.infrastructure.catalog.catalog_registry.entry_to_definition") as map_defn:
        map_defn.return_value = AgentDefinition(
            name="consultant",
            description="x",
            role="worker",
            system_prompt="prompt",
        )
        registry = catalog_registry.load_catalog_registry()

    assert registry.names() == ["consultant"]
    catalog.list_agents.assert_called_once_with(enabled_only=True)
