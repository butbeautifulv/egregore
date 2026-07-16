from __future__ import annotations

import pytest


@pytest.mark.unit
def test_config_computed_fields(monkeypatch):
    from bootstrap.settings import Settings, get_settings

    settings = Settings(DEEPSEEK_API_KEY="", OPENAI_API_KEY="openai-key", REDIS_PASSWORD="")

    assert settings.llm_api_key == "openai-key"
    assert settings.postgres_url == "postgresql://postgres:password@localhost:5432/egregore"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.persistence_connector == "auto"

    get_settings.cache_clear()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "cached-key")
    try:
        assert get_settings().llm_api_key == "cached-key"
    finally:
        get_settings.cache_clear()

    local = Settings(
        LLM_BASE_URL="http://10.8.185.186:11612/v1",
        DEEPSEEK_API_KEY="",
        OPENAI_API_KEY="",
        OPENROUTER_API_KEY="",
        ANTHROPIC_API_KEY="",
        GEMINI_API_KEY="",
        AI_APIKEY="",
    )
    assert local.llm_api_key == "EMPTY"
    defaults = Settings(WORKER_REPLICAS=2)
    assert defaults.worker_idle_timeout == 0.0
    assert defaults.worker_replicas == 2
    assert defaults.llm_request_timeout == 120.0
