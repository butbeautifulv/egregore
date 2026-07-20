from __future__ import annotations

import pytest


@pytest.mark.unit
def test_kafka_config_defaults():
    from bootstrap.settings import Settings

    settings = Settings()
    assert settings.kafka_bootstrap_servers == "localhost:19092"
    assert settings.use_kafka is False


@pytest.mark.unit
def test_kafka_config_from_env(monkeypatch):
    from bootstrap.settings import Settings, get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
    monkeypatch.setenv("USE_KAFKA", "true")
    try:
        settings = Settings()
        assert settings.kafka_bootstrap_servers == "redpanda:9092"
        assert settings.use_kafka is True
        assert get_settings().use_kafka is True
    finally:
        get_settings.cache_clear()
