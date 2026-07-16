from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from bootstrap.settings import get_settings
from cys_core.application.use_cases.engagement_planner import ASYNC_PLANNER_PENDING
from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus, PlanStrategy
from cys_core.domain.events.models import RoutingDecision, SecurityEvent
from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_engagement_start_returns_202(monkeypatch):
    from interfaces.api.app import create_app

    event = SecurityEvent(
        id="evt-async-1",
        type="engagement.start",
        source="",
        severity="medium",
        payload={"goal": "test", "plan_strategy": "meta_llm"},
        correlation_id="inv-async-1",
    )
    decision = RoutingDecision(
        event_id=event.id,
        personas=[],
        playbook_id="engagement-meta-llm",
        notify_control=True,
        reason=ASYNC_PLANNER_PENDING,
    )
    engagement = Engagement(
        id="inv-async-1",
        tenant_id="default",
        profile_id="cybersec-soc",
        domain_id="",
        goal="test",
        mode=EngagementMode.ASYNC,
        status=EngagementStatus.PLANNING,
        correlation_id="inv-async-1",
        plan_strategy=PlanStrategy.META_LLM,
    )
    fake_start = MagicMock()
    fake_start.execute = AsyncMock(return_value=(engagement, decision, []))
    import bootstrap.container as container_mod

    catalog = MagicMock()
    catalog.bus_recipients = []
    container_mod._container = SimpleNamespace(
        get_start_engagement=lambda: fake_start,
        get_job_store=lambda: InMemoryJobStore(),
        get_agent_catalog=lambda: catalog,
        settings=get_settings(),
    )
    monkeypatch.setattr(
        "bootstrap.container.get_container",
        lambda: container_mod._container,
    )
    monkeypatch.setattr(
        "interfaces.api.app.get_container",
        lambda: container_mod._container,
    )
    store = SimpleNamespace(
        record_event=lambda _e: None,
        record_investigation_update=lambda _p: None,
    )
    monkeypatch.setattr("interfaces.api.app.get_status_store", lambda: store)

    app = create_app(ingress=MagicMock())
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/events",
            json={
                "event_type": "engagement.start",
                "payload": {"goal": "test", "plan_strategy": "meta_llm"},
                "correlation_id": "inv-async-1",
            },
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["accepted"] is True
        assert body["planner_status"] == "planning"
        assert body["job_ids"] == []
        assert body["investigation_id"] == "inv-async-1"
