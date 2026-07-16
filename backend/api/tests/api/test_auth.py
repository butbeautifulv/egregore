from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_api_auth_disabled_allows_requests(monkeypatch):
    from interfaces.api.app import create_app

    async def fake_aingest(event_type, payload, **kwargs):
        return (
            SimpleNamespace(model_dump=lambda: {"id": "e1", "type": event_type}),
            SimpleNamespace(model_dump=lambda: {"personas": ["soc"]}),
            ["job-1"],
        )

    monkeypatch.setenv("AUTH_ENABLED", "0")
    from bootstrap.settings import get_settings

    get_settings.cache_clear()

    app = create_app(ingress=SimpleNamespace(aingest=fake_aingest))
    client = TestClient(app)
    response = client.post("/events", json={"event_type": "siem.alert", "payload": {}})
    assert response.status_code == 200


@pytest.mark.unit
def test_api_auth_requires_bearer(auth_settings):
    from interfaces.api.app import create_app

    app = create_app(ingress=SimpleNamespace(aingest=lambda *a, **k: None))
    client = TestClient(app)
    response = client.post("/events", json={"event_type": "siem.alert", "payload": {}})
    assert response.status_code == 401


@pytest.mark.unit
def test_api_auth_ingress_role_required(auth_settings):
    from interfaces.api.app import create_app

    token = auth_settings["token"]([auth_settings["roles"]["reader"]])
    app = create_app(ingress=SimpleNamespace(aingest=lambda *a, **k: None))
    client = TestClient(app)
    response = client.post(
        "/events",
        json={"event_type": "siem.alert", "payload": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_api_auth_ingress_success(auth_settings):
    from interfaces.api.app import create_app

    async def fake_aingest(event_type, payload, **kwargs):
        return (
            SimpleNamespace(model_dump=lambda: {"id": "e1", "type": event_type}),
            SimpleNamespace(model_dump=lambda: {"personas": ["soc"]}),
            ["job-1"],
        )

    # No interfaces.control_plane module here (worker-only) — app.py's
    # in-process critic/coordinator invocation catches that ImportError and
    # logs a warning instead of crashing, so nothing needs patching out.
    token = auth_settings["token"]([auth_settings["roles"]["ingress"]])
    app = create_app(ingress=SimpleNamespace(aingest=fake_aingest))
    client = TestClient(app)
    response = client.post(
        "/events",
        json={"event_type": "siem.alert", "payload": {"x": 1}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["job_ids"] == ["job-1"]


@pytest.mark.unit
def test_api_auth_reader_can_read_status(auth_settings, monkeypatch):
    from interfaces.api.app import create_app

    monkeypatch.setattr(
        "interfaces.api.app.get_status_store",
        lambda: SimpleNamespace(snapshot=lambda: {"events": 0}),
    )
    token = auth_settings["token"]([auth_settings["roles"]["reader"]])
    app = create_app(ingress=SimpleNamespace(aingest=lambda *a, **k: None))
    client = TestClient(app)
    response = client.get("/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
