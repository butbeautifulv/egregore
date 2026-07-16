from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_post_event_and_status():
    from interfaces.api.app import create_app

    async def fake_aingest(event_type, payload, **kwargs):
        return (
            SimpleNamespace(model_dump=lambda: {"id": "e1", "type": event_type}),
            SimpleNamespace(model_dump=lambda: {"personas": ["soc"]}),
            ["job-1"],
        )

    ingress = SimpleNamespace(aingest=fake_aingest)
    app = create_app(ingress=ingress)

    from httpx import ASGITransport, AsyncClient

    # No interfaces.control_plane module here (worker-only) — app.py's
    # in-process critic/coordinator invocation catches that ImportError and
    # logs a warning instead of crashing, so nothing needs patching out.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/events", json={"event_type": "siem.alert", "payload": {"x": 1}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_ids"] == ["job-1"]
        status = await client.get("/status")
        assert status.status_code == 200
