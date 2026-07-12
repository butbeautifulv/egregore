from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from interfaces.api.app import create_app


@pytest.mark.unit
def test_health_infra_returns_queue_and_egress(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQueue:
        name = "redis"

        @property
        def active_backend(self) -> str:
            return "redis"

        def queue_depth(self) -> int:
            return 3

    class FakeEgress:
        @property
        def active_backend(self) -> str:
            return "redis"

    class FakeJobStore:
        def count_running(self) -> int:
            return 1

    class FakeTransport:
        name = "redis"

        @property
        def active_backend(self) -> str:
            return "redis"

    class FakeContainer:
        def get_engagement_egress(self) -> FakeEgress:
            return FakeEgress()

        def get_job_store(self) -> FakeJobStore:
            return FakeJobStore()

        def get_job_queue(self) -> FakeQueue:
            return FakeQueue()

        def get_authz_service(self) -> MagicMock:
            authz = MagicMock()
            authz.ping.return_value = True
            authz.mode = "off"
            return authz

        def get_agent_catalog(self) -> MagicMock:
            catalog = MagicMock()
            catalog.bus_recipients = []
            return catalog

        def get_engagement_state_store(self) -> MagicMock:
            return MagicMock()

        def get_reconcile_stuck_engagements(self) -> MagicMock:
            return MagicMock(execute=AsyncMock())

        def get_trace_backend(self) -> MagicMock:
            backend = MagicMock()
            backend.flush = MagicMock()
            backend.shutdown = MagicMock()
            return backend

    container = FakeContainer()
    monkeypatch.setattr("bootstrap.container.get_container", lambda: container)
    monkeypatch.setattr("interfaces.api.app.get_container", lambda: container)
    monkeypatch.setattr("cys_core.infrastructure.bus_transport.get_bus_transport", lambda: FakeTransport())
    monkeypatch.setattr("interfaces.api.app.setup_otel", lambda **_: None)
    monkeypatch.setattr("interfaces.api.app.refresh_platform_gauges", lambda **_k: None)
    monkeypatch.setattr("cys_core.observability.catalog_drift.verify_critic_intel_recipient", lambda _c: True)

    from unittest.mock import AsyncMock

    monkeypatch.setattr("bootstrap.bus_lifecycle.wire_async_bus", AsyncMock())

    from fastapi.testclient import TestClient

    with TestClient(create_app(ingress=MagicMock())) as client:
        response = client.get("/health/infra")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["queue"]["backend"] == "redis"
    assert body["queue"]["depth"] == 3
    assert body["egress"]["backend"] == "redis"
    assert body["workers_hint"] == "processing"
