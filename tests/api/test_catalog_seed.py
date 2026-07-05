from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_catalog_seed_endpoint_returns_cybersec_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    from interfaces.api.app import create_app

    seed_result = {
        "profile": {"id": "cybersec-soc", "name": "Cybersec SOC", "default_personas": ["consultant"]},
        "seeded": 4,
        "skills": 2,
        "plans": 1,
        "mcp_servers": 1,
        "tools": 5,
    }
    mock_seed = MagicMock()
    mock_seed.execute.return_value = seed_result
    monkeypatch.setattr(
        "bootstrap.container.Container.get_seed_catalog",
        lambda self: mock_seed,
    )

    app = create_app()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/catalog/seed")

    assert resp.status_code == 200
    body = resp.json()
    assert body["profile"]["id"] == "cybersec-soc"
    assert body["seeded"] >= 1


@pytest.mark.unit
def test_seed_catalog_use_case_loads_cybersec_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    from cys_core.application.use_cases.seed_catalog import SeedCatalog
    from cys_core.domain.catalog.models import AgentCatalogEntry, ProfilePack
    from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID

    profile = ProfilePack(id=DEFAULT_PROFILE_ID, name="Cybersec SOC", default_personas=["consultant"])
    entries = [
        AgentCatalogEntry(name="consultant", profile_id=DEFAULT_PROFILE_ID, enabled=True),
    ]
    catalog = MagicMock()
    seed_loaders = MagicMock()
    seed_loaders.load_skills.return_value = []
    seed_loaders.load_plans.return_value = []
    seed_loaders.load_mcp_servers.return_value = []
    tool_catalog = MagicMock()
    result = SeedCatalog(
        catalog,
        tool_catalog=tool_catalog,
        seed_loaders=seed_loaders,
        load_profile_pack=lambda: (profile, entries),
        load_tools_for_seed=lambda _profile_id: [],
        reload=lambda: None,
    ).execute()

    assert result["profile"]["id"] == "cybersec-soc"
    assert result["seeded"] == 1
    catalog.seed.assert_called_once()
    tool_catalog.seed.assert_called_once()
