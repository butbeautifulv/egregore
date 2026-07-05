from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from interfaces.api.app import create_app


@pytest.mark.unit
def test_lifespan_flushes_trace_backend(monkeypatch):
    calls: list[str] = []

    class FakeBackend:
        def flush(self):
            calls.append("flush")

        def shutdown(self):
            calls.append("shutdown")

    fake_container = type("C", (), {"get_trace_backend": lambda self: FakeBackend()})()
    import bootstrap.container as container_mod

    container_mod._container = fake_container
    monkeypatch.setattr("bootstrap.container.get_container", lambda: fake_container)
    monkeypatch.setattr("interfaces.api.app.get_container", lambda: fake_container)
    monkeypatch.setattr("interfaces.api.app.setup_otel", lambda **_: None)
    monkeypatch.setattr("interfaces.api.app.refresh_platform_gauges", lambda: None)
    monkeypatch.setattr("bootstrap.bus_lifecycle.wire_async_bus", AsyncMock())

    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient

    with TestClient(create_app(ingress=MagicMock())) as client:
        client.get("/health")
    assert "flush" in calls
    assert "shutdown" in calls
