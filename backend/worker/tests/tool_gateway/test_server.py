from __future__ import annotations

import pytest

from tests.tool_gateway.gateway_client import GatewayTestClient


@pytest.mark.unit
def test_gateway_health():
    client = GatewayTestClient()
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.unit
def test_gateway_invoke_success():
    client = GatewayTestClient()
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
    body = response.json()
    assert body["success"] is True
    assert body["tool_name"] == "dedup_alerts"
    assert "RETRIEVED_TOOL_DATA" in body["sanitized_payload"]
    assert "BEGIN_RETRIEVED_CONTENT" in body["sanitized_payload"]


@pytest.mark.unit
def test_gateway_invoke_denies_host_sandbox():
    client = GatewayTestClient()
    response = client.post(
        "/invoke",
        json={
            "tool_name": "dedup_alerts",
            "args": {},
            "persona": "soc",
            "sandbox_id": "host",
        },
    )
    body = response.json()
    assert body["success"] is False
    assert "sandbox" in body["error"].lower()
