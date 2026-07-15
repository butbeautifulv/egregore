from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.gateways.tool.server import create_app


@pytest.mark.unit
def test_gateway_auth_disabled_invoke_works():
    from bootstrap.container import get_container

    get_container()
    client = TestClient(create_app())
    response = client.post(
        "/invoke",
        json={
            "tool_name": "dedup_alerts",
            "args": {"alerts_text": "alert one"},
            "persona": "soc",
            "sandbox_id": "sandbox-abc",
        },
    )
    assert response.status_code == 200


@pytest.mark.unit
def test_gateway_auth_health_unauthenticated(auth_settings):
    client = TestClient(create_app())
    assert client.get("/health").status_code == 200


@pytest.mark.unit
def test_gateway_auth_invoke_requires_token(auth_settings):
    client = TestClient(create_app())
    response = client.post(
        "/invoke",
        json={
            "tool_name": "dedup_alerts",
            "args": {"alerts_text": "alert one"},
            "persona": "soc",
            "sandbox_id": "sandbox-abc",
        },
    )
    assert response.status_code == 401


@pytest.mark.unit
def test_gateway_auth_invoke_wrong_role(auth_settings):
    token = auth_settings["token"]([auth_settings["roles"]["reader"]])
    client = TestClient(create_app())
    response = client.post(
        "/invoke",
        json={
            "tool_name": "dedup_alerts",
            "args": {"alerts_text": "alert one"},
            "persona": "soc",
            "sandbox_id": "sandbox-abc",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_gateway_auth_invoke_success(auth_settings):
    token = auth_settings["token"]([auth_settings["roles"]["gateway"]])
    client = TestClient(create_app())
    response = client.post(
        "/invoke",
        json={
            "tool_name": "dedup_alerts",
            "args": {"alerts_text": "alert one"},
            "persona": "soc",
            "sandbox_id": "sandbox-abc",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
