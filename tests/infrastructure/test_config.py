from __future__ import annotations

import pytest


@pytest.mark.unit
def test_config_computed_fields(monkeypatch):
    from bootstrap.settings import Settings, get_settings

    settings = Settings(OPENAI_API_KEY="openai-key", REDIS_PASSWORD="")

    assert settings.llm_api_key == "openai-key"
    assert settings.postgres_url == "postgresql://postgres:password@localhost:5432/cys_agi"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.persistence_connector == "auto"

    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", "cached-key")
    try:
        assert get_settings().llm_api_key == "cached-key"
    finally:
        get_settings.cache_clear()
