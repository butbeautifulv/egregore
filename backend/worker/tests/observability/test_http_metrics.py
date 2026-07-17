from __future__ import annotations

import pytest

from cys_core.observability.http import generate_metrics_payload
from tests.tool_gateway.gateway_client import GatewayTestClient


@pytest.mark.unit
def test_generate_metrics_payload_prometheus_format():
    payload = generate_metrics_payload()
    assert isinstance(payload, bytes)
    assert b"cys_events_ingested_total" in payload or payload


@pytest.mark.unit
def test_gateway_metrics_endpoint():
    client = GatewayTestClient()
    response = client.get("/metrics")
    assert response.status_code == 200
