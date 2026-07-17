from __future__ import annotations

import pytest

from tests.tool_gateway.gateway_client import GatewayTestClient


@pytest.mark.integration
def test_invoke_sanitizes_and_returns_payload():
    client = GatewayTestClient()
    response = client.post(
        "/invoke",
        json={
            "tool_name": "enrich_ioc",
            "args": {"ioc": "1.2.3.4"},
            "persona": "network",
            "sandbox_id": "sandbox-1",
        },
    )
    body = response.json()
    assert body["success"] is True
    assert body["sanitized_payload"]
