from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.application.use_cases.dispatch_event import ASYNC_PLANNER_PENDING
from cys_core.domain.events.models import RoutingDecision, SecurityEvent


def _fake_ingress_async() -> SimpleNamespace:
    event = SecurityEvent(
        id="evt-async-1",
        type="manual.investigation",
        source="",
        severity="medium",
        payload={"goal": "test"},
        correlation_id="inv-async-1",
    )
    decision = RoutingDecision(
        event_id=event.id,
        personas=[],
        playbook_id="manual-investigation",
        notify_control=True,
        reason=ASYNC_PLANNER_PENDING,
    )
    ingress = SimpleNamespace(
        aingest=AsyncMock(return_value=(event, decision, [])),
        plan_investigation=SimpleNamespace(),
        orchestrator=SimpleNamespace(),
    )
    return ingress


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_manual_investigation_returns_202(monkeypatch):
    from interfaces.api.app import create_app

    monkeypatch.setattr(
        "interfaces.api.app.complete_manual_investigation_planning",
        AsyncMock(return_value=[]),
    )
    store = SimpleNamespace(
        record_event=lambda _e: None,
        record_investigation_update=lambda _p: None,
    )
    monkeypatch.setattr("interfaces.api.app.get_status_store", lambda: store)

    app = create_app(ingress=_fake_ingress_async())
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/events",
            json={
                "event_type": "manual.investigation",
                "payload": {"goal": "test"},
                "correlation_id": "inv-async-1",
            },
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["accepted"] is True
        assert body["planner_status"] == "planning"
        assert body["job_ids"] == []
