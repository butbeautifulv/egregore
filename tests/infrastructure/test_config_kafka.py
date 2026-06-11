from __future__ import annotations

import pytest


@pytest.mark.unit
def test_kafka_config_defaults():
    from config import Settings

    settings = Settings()

    assert settings.kafka_bootstrap_servers == "localhost:19092"
    assert settings.use_kafka is False


@pytest.mark.unit
def test_kafka_config_env_override(monkeypatch):
    from config import Settings, get_settings

    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
    monkeypatch.setenv("USE_KAFKA", "true")

    settings = Settings()
    assert settings.kafka_bootstrap_servers == "redpanda:9092"
    assert settings.use_kafka is True

    get_settings.cache_clear()
    try:
        cached = get_settings()
        assert cached.kafka_bootstrap_servers == "redpanda:9092"
        assert cached.use_kafka is True
    finally:
        get_settings.cache_clear()
