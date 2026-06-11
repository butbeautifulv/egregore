from __future__ import annotations

import pytest


@pytest.mark.unit
def test_kafka_config_defaults_and_env(monkeypatch):
    from config import Settings, get_settings

    settings = Settings()

    assert settings.use_kafka is False
    assert settings.kafka_bootstrap_servers == "localhost:19092"

    get_settings.cache_clear()
    monkeypatch.setenv("USE_KAFKA", "true")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
    try:
        cached_settings = get_settings()
        assert cached_settings.use_kafka is True
        assert cached_settings.kafka_bootstrap_servers == "redpanda:9092"
    finally:
        get_settings.cache_clear()
