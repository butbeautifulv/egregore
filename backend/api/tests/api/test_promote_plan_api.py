from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.domain.catalog.models import PlanCatalogEntry
from cys_core.domain.engagement.models import Engagement, EngagementStatus


@pytest.mark.unit
@pytest.mark.asyncio
async def test_promote_engagement_plan_saves_catalog_entry(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from interfaces.api.app import create_app

    engagement = Engagement(
        id="eng-promote",
        tenant_id="default",
        goal="Investigate lateral movement",
        status=EngagementStatus.RUNNING,
        planner_plan=["soc", "hunter"],
        planner_rationale="Start with SOC triage then hunt.",
        profile_id="cybersec-soc",
    )
    store = MagicMock()
    store.get.return_value = engagement
    saved_entry = PlanCatalogEntry(
        id="custom-plan",
        name="Investigate lateral movement",
        description="Start with SOC triage then hunt.",
        rules=[
            {
                "event_types": ["manual.investigation", "engagement.start"],
                "personas": ["soc", "hunter"],
                "description": "Start with SOC triage then hunt.",
            }
        ],
        profile_id="cybersec-soc",
    )
    mutation = MagicMock()
    mutation.upsert_plan.return_value = saved_entry
    monkeypatch.setattr(
        "interfaces.api.engagements.get_container",
        lambda: MagicMock(
            get_engagement_state_store=lambda: store,
            get_catalog_mutation_service=lambda: mutation,
        ),
    )

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/engagements/eng-promote/promote-plan",
            json={"plan_id": "custom-plan", "activate": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "custom-plan"
        assert body["rules"][0]["personas"] == ["soc", "hunter"]
        mutation.upsert_plan.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_promote_engagement_plan_rejects_empty_planner_plan(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from interfaces.api.app import create_app

    engagement = Engagement(
        id="eng-empty",
        tenant_id="default",
        goal="No plan yet",
        status=EngagementStatus.RUNNING,
        planner_plan=[],
    )
    store = MagicMock()
    store.get.return_value = engagement
    monkeypatch.setattr(
        "interfaces.api.engagements.get_container",
        lambda: MagicMock(
            get_engagement_state_store=lambda: store,
            get_catalog_mutation_service=lambda: MagicMock(),
        ),
    )

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/engagements/eng-empty/promote-plan",
            json={"plan_id": "noop-plan", "activate": False},
        )
        assert resp.status_code == 400
        assert "planner_plan" in resp.json()["detail"].lower()
