from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from interfaces.control_plane.status_store import MemoryStatusStore


@pytest.mark.unit
def test_memory_status_store_notifies_subscribers():
    store = MemoryStatusStore()
    received: list[dict] = []
    store.subscribe(lambda _kind, event: received.append(event))
    store.record_event({"id": "evt-stream", "type": "siem.alert"})
    assert received
    assert received[0]["kind"] == "event"
    assert received[0]["payload"]["id"] == "evt-stream"


@pytest.mark.unit
def test_status_stream_route_registered():
    from interfaces.api.app import create_app

    app = create_app(ingress=SimpleNamespace(aingest=AsyncMock()))
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/status/stream" in paths
