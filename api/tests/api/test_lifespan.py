from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bootstrap.settings import get_settings
from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore
from interfaces.api.app import create_app


@pytest.mark.unit
def test_lifespan_flushes_trace_backend(monkeypatch):
    calls: list[str] = []

    class FakeBackend:
        def flush(self):
            calls.append("flush")

        def shutdown(self):
            calls.append("shutdown")

    catalog = MagicMock()
    catalog.bus_recipients = []
    fake_container = type(
        "C",
        (),
        {
            "get_trace_backend": lambda self: FakeBackend(),
            "get_job_store": lambda self: InMemoryJobStore(),
            "get_agent_catalog": lambda self: catalog,
            "get_engagement_state_store": lambda self: MagicMock(),
            "get_reconcile_stuck_engagements": lambda self: MagicMock(execute=AsyncMock()),
            "settings": get_settings(),
        },
    )()
    import bootstrap.container as container_mod

    container_mod._container = fake_container
    monkeypatch.setattr("bootstrap.container.get_container", lambda: fake_container)
    monkeypatch.setattr("interfaces.api.app.get_container", lambda: fake_container)
    monkeypatch.setattr("interfaces.api.app.setup_otel", lambda **_: None)
    monkeypatch.setattr("interfaces.api.app.refresh_platform_gauges", lambda **_k: None)
    monkeypatch.setattr("cys_core.observability.catalog_drift.verify_critic_intel_recipient", lambda _c: True)
    monkeypatch.setattr("bootstrap.bus_lifecycle.wire_async_bus", AsyncMock())

    from fastapi.testclient import TestClient

    with TestClient(create_app(ingress=MagicMock())) as client:
        client.get("/health")
    assert "flush" in calls
    assert "shutdown" in calls
