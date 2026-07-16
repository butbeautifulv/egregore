from __future__ import annotations

import pytest

from cys_core.infrastructure.k8s_sandbox import K8sSandboxConnector
from cys_core.infrastructure.sandbox import LocalSandboxConnector, reset_sandbox_connector_cache


@pytest.mark.unit
def test_get_sandbox_connector_local_default(monkeypatch):
    from bootstrap.settings import get_settings, settings

    get_settings.cache_clear()
    reset_sandbox_connector_cache()
    monkeypatch.setenv("SANDBOX_CONNECTOR", "local")
    settings.sandbox_connector = "local"
    try:
        from cys_core.infrastructure.sandbox import get_sandbox_connector

        assert isinstance(get_sandbox_connector(), LocalSandboxConnector)
    finally:
        reset_sandbox_connector_cache()
        get_settings.cache_clear()


@pytest.mark.unit
def test_get_sandbox_connector_k8s(monkeypatch):
    from bootstrap.settings import get_settings, settings

    get_settings.cache_clear()
    reset_sandbox_connector_cache()
    monkeypatch.setenv("SANDBOX_CONNECTOR", "k8s")
    settings.sandbox_connector = "k8s"
    try:
        from cys_core.infrastructure.sandbox import get_sandbox_connector

        assert isinstance(get_sandbox_connector(), K8sSandboxConnector)
    finally:
        reset_sandbox_connector_cache()
        get_settings.cache_clear()
