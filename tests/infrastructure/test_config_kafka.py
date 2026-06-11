from __future__ import annotations

import pytest


@pytest.mark.unit
def test_kafka_config_defaults():
    from config import Settings

    settings = Settings()

    assert settings.use_kafka is False
    assert settings.kafka_bootstrap_servers == "localhost:9092"


@pytest.mark.unit
def test_kafka_config_from_env():
    from config import Settings

    settings = Settings(
        USE_KAFKA="true",
        KAFKA_BOOTSTRAP_SERVERS="redpanda:29092,redpanda2:29092",
    )

    assert settings.use_kafka is True
    assert settings.kafka_bootstrap_servers == "redpanda:29092,redpanda2:29092"


@pytest.mark.unit
def test_kafka_config_cached(monkeypatch):
    from config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("USE_KAFKA", "true")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "cached:9092")
    try:
        cached = get_settings()
        assert cached.use_kafka is True
        assert cached.kafka_bootstrap_servers == "cached:9092"
    finally:
        get_settings.cache_clear()
