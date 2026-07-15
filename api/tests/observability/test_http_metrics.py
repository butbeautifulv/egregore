from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cys_core.observability.http import mount_metrics, render_metrics


@pytest.mark.unit
def test_render_metrics_prometheus_format():
    response = render_metrics()
    assert response.media_type.startswith("text/plain")
    assert b"cys_events_ingested_total" in response.body or response.body


@pytest.mark.unit
def test_mount_metrics_endpoint():
    app = FastAPI()
    mount_metrics(app)
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
