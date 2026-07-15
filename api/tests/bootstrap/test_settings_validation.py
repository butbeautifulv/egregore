from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from bootstrap.settings import Settings


@pytest.mark.unit
def test_settings_accepts_test_stage_defaults() -> None:
    settings = Settings(STAGE="test")
    assert settings.stage == "test"
    assert settings.worker_job_timeout >= settings.llm_request_timeout


@pytest.mark.unit
def test_settings_requires_kafka_bootstrap_when_kafka_enabled() -> None:
    with pytest.raises(ValidationError, match="KAFKA_BOOTSTRAP_SERVERS"):
        Settings(STAGE="test", USE_KAFKA=True, KAFKA_BOOTSTRAP_SERVERS="")


@pytest.mark.unit
def test_settings_rejects_worker_timeout_below_llm_timeout() -> None:
    with pytest.raises(ValidationError, match="WORKER_JOB_TIMEOUT"):
        Settings(STAGE="test", LLM_REQUEST_TIMEOUT=120.0, WORKER_JOB_TIMEOUT=60.0)


@pytest.mark.unit
def test_settings_rejects_invalid_control_mode() -> None:
    with pytest.raises(ValidationError, match="CONTROL_MODE"):
        Settings(STAGE="test", CONTROL_MODE="invalid")


@pytest.mark.unit
def test_settings_prod_rejects_default_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_MEMORY_FALLBACK", "false")
    with pytest.raises(ValidationError, match="REDIS_PASSWORD"):
        Settings(
            STAGE="prod",
            USE_MEMORY_FALLBACK=False,
            REDIS_PASSWORD="password",
            POSTGRES_PASSWORD="secret",
            BUS_SIGNING_KEY="secret-key",
        )


@pytest.mark.unit
def test_settings_prod_rejects_memory_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_MEMORY_FALLBACK", "true")
    with pytest.raises(ValidationError, match="USE_MEMORY_FALLBACK"):
        Settings(
            STAGE="prod",
            USE_MEMORY_FALLBACK=True,
            REDIS_PASSWORD="secret-redis",
            POSTGRES_PASSWORD="secret-pg",
            BUS_SIGNING_KEY="secret-bus",
        )


@pytest.mark.unit
def test_settings_repr_hides_secret_values() -> None:
    settings = Settings(
        STAGE="test",
        REDIS_PASSWORD="super-secret",
        POSTGRES_PASSWORD="super-secret",
    )
    rendered = repr(settings)
    assert "super-secret" not in rendered
    assert "stage='test'" in rendered


@pytest.mark.unit
def test_settings_redis_url_uses_secret_password() -> None:
    settings = Settings(STAGE="test", REDIS_PASSWORD="redis-pass")
    assert settings.redis_url == "redis://:redis-pass@localhost:6379/0"


@pytest.mark.unit
def test_settings_gateway_token_secret_str() -> None:
    settings = Settings(STAGE="test", GATEWAY_ACCESS_TOKEN="token-123")
    assert settings.gateway_access_token == SecretStr("token-123")
