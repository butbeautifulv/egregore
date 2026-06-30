from __future__ import annotations

import pytest

from bootstrap.settings import Settings
from cys_core.observability import langfuse_client


@pytest.mark.unit
def test_langfuse_enabled_requires_both_keys():
    settings = Settings(
        LANGFUSE_PUBLIC_KEY="pk-test",
        LANGFUSE_SECRET_KEY="sk-test",
    )
    assert settings.langfuse_enabled is True
    assert settings.resolved_langfuse_public_key == "pk-test"


@pytest.mark.unit
def test_langfuse_deprecated_api_key_fallback():
    settings = Settings(
        LANGFUSE_PUBLIC_KEY="",
        LANGFUSE_API_KEY="pk-legacy",
        LANGFUSE_SECRET_KEY="sk-test",
    )
    assert settings.resolved_langfuse_public_key == "pk-legacy"
    assert settings.langfuse_enabled is True


@pytest.mark.unit
def test_langfuse_disabled_without_secret():
    settings = Settings(LANGFUSE_PUBLIC_KEY="pk-only", LANGFUSE_SECRET_KEY="")
    assert settings.langfuse_enabled is False


@pytest.mark.unit
def test_langfuse_base_url_overrides_host():
    settings = Settings(
        LANGFUSE_HOST="http://localhost:3000",
        LANGFUSE_BASE_URL="http://localhost:3001",
    )
    assert settings.resolved_langfuse_host == "http://localhost:3001"


@pytest.mark.unit
def test_get_langfuse_callback_handler_disabled(monkeypatch):
    monkeypatch.setattr(langfuse_client.settings, "langfuse_public_key", "")
    monkeypatch.setattr(langfuse_client.settings, "langfuse_secret_key", "")
    langfuse_client.reset_langfuse_client_cache()
    assert langfuse_client.get_langfuse_callback_handler() is None


@pytest.mark.unit
def test_flush_langfuse_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(langfuse_client.settings, "langfuse_public_key", "")
    monkeypatch.setattr(langfuse_client.settings, "langfuse_secret_key", "")
    langfuse_client.flush_langfuse()
