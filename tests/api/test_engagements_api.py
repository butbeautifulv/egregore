from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.domain.engagement.models import EngagementMode, EngagementRequest, PlanStrategy
from cys_core.domain.events.models import RoutingDecision


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_engagement_returns_job_ids(monkeypatch):
    from interfaces.api.app import create_app

    from cys_core.domain.engagement.models import Engagement, EngagementStatus

    engagement = Engagement(
        id="eng-1",
        tenant_id="default",
        profile_id="cybersec-soc",
        domain_id="",
        goal="test goal",
        mode=EngagementMode.ASYNC,
        status=EngagementStatus.ENQUEUED,
        correlation_id="eng-1",
        plan_strategy=PlanStrategy.DECLARATIVE,
        job_ids=["job-soc"],
    )
    decision = RoutingDecision(
        event_id="eng-1",
        personas=["soc"],
        playbook_id="engagement-default",
        notify_control=True,
        reason="declarative",
    )
    fake_start = MagicMock()
    fake_start.execute = AsyncMock(return_value=(engagement, decision, ["job-soc"]))
    monkeypatch.setattr(
        "interfaces.api.engagements.get_container",
        lambda: MagicMock(get_start_engagement=lambda: fake_start),
    )

    app = create_app()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/engagements",
            json={"goal": "test goal", "plan_strategy": "declarative"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["engagement_id"] == "eng-1"
        assert body["job_ids"] == ["job-soc"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_engagements_returns_recent(monkeypatch):
    from interfaces.api.app import create_app

    from cys_core.domain.engagement.models import Engagement, EngagementStatus

    store = MagicMock()
    store.list_recent.return_value = [
        Engagement(
            id="eng-1",
            tenant_id="default",
            goal="goal one",
            status=EngagementStatus.RUNNING,
            completed_personas=["soc"],
        )
    ]
    monkeypatch.setattr(
        "interfaces.api.engagements.get_container",
        lambda: MagicMock(get_engagement_state_store=lambda: store),
    )

    app = create_app()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/engagements?tenant_id=default")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["engagements"]) == 1
        assert body["engagements"][0]["engagement_id"] == "eng-1"
        assert body["engagements"][0]["goal"] == "goal one"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_engagement_preserves_closed_status_with_egress(monkeypatch):
    from interfaces.api.app import create_app

    from cys_core.domain.engagement.models import Engagement, EngagementStatus

    engagement = Engagement(
        id="eng-closed",
        tenant_id="default",
        goal="done goal",
        status=EngagementStatus.CLOSED,
        completed_personas=["consultant"],
        planner_plan=["consultant"],
    )
    fake_start = MagicMock()
    egress = MagicMock()
    egress.snapshot.return_value = [{"phase": "job_finished", "payload": {"persona": "consultant"}}]
    monkeypatch.setattr(
        "interfaces.api.engagements.get_container",
        lambda: MagicMock(
            get_engagement_state_store=lambda: SimpleNamespace(
                get=lambda tenant_id, engagement_id: engagement if engagement_id == "eng-closed" else None,
            ),
            get_engagement_egress=lambda: egress,
        ),
    )
    monkeypatch.setattr("cys_core.observability.catalog_drift.verify_critic_intel_recipient", lambda _c: True)

    app = create_app()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/engagements/eng-closed")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "closed"
        assert body["latest_phase"] == "job_finished"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_engagement_events_returns_snapshot(monkeypatch):
    from interfaces.api.app import create_app

    from cys_core.domain.engagement.models import Engagement, EngagementStatus

    engagement = Engagement(
        id="eng-events",
        tenant_id="default",
        goal="events goal",
        status=EngagementStatus.CLOSED,
    )
    fake_start = MagicMock()
    fake_start.get = MagicMock(return_value=engagement)
    egress = MagicMock()
    egress.snapshot.return_value = [
        {"type": "control", "payload": {"job_id": "critic:eng-events", "verdict": {"passed": True}}}
    ]
    monkeypatch.setattr(
        "interfaces.api.engagements.get_container",
        lambda: MagicMock(
            get_start_engagement=lambda: fake_start,
            get_engagement_egress=lambda: egress,
        ),
    )

    app = create_app()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/engagements/eng-events/events")
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["type"] == "control"
        assert body[0]["payload"]["job_id"] == "critic:eng-events"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_engagement_memory_empty(monkeypatch):
    from interfaces.api.app import create_app

    from cys_core.domain.engagement.models import Engagement, EngagementStatus
    from cys_core.domain.memory.services import MemoryReadService
    from cys_core.infrastructure.memory.stores import InMemoryEpisodicMemoryStore

    engagement = Engagement(
        id="eng-mem",
        tenant_id="default",
        goal="memory goal",
        status=EngagementStatus.RUNNING,
    )
    fake_start = MagicMock()
    fake_start.get = MagicMock(return_value=engagement)
    episodic = InMemoryEpisodicMemoryStore()
    reader = MemoryReadService(episodic)
    container = MagicMock(
        get_start_engagement=lambda: fake_start,
        get_memory_read_service=lambda: reader,
    )
    monkeypatch.setattr("interfaces.api.engagements.get_container", lambda: container)

    app = create_app()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/engagements/eng-mem/memory")
        assert resp.status_code == 200
        assert resp.json()["entries"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_engagement_memory_filters_by_agent(monkeypatch):
    from interfaces.api.app import create_app

    from cys_core.domain.engagement.models import Engagement, EngagementStatus
    from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
    from cys_core.infrastructure.memory.stores import InMemoryEpisodicMemoryStore

    engagement = Engagement(
        id="eng-mem-filter",
        tenant_id="default",
        goal="memory filter goal",
        status=EngagementStatus.RUNNING,
    )
    fake_start = MagicMock()
    fake_start.get = MagicMock(return_value=engagement)
    episodic = InMemoryEpisodicMemoryStore()
    writer = MemoryWriteService(episodic)
    writer.append_finding(
        tenant_id="default",
        investigation_id="eng-mem-filter",
        source_agent="soc",
        source_job_id="job-soc",
        finding={"summary": "soc finding"},
        trust_score=0.9,
    )
    writer.append_finding(
        tenant_id="default",
        investigation_id="eng-mem-filter",
        source_agent="hunter",
        source_job_id="job-hunter",
        finding={"summary": "hunter finding"},
        trust_score=0.8,
    )
    reader = MemoryReadService(episodic)
    container = MagicMock(
        get_start_engagement=lambda: fake_start,
        get_memory_read_service=lambda: reader,
    )
    monkeypatch.setattr("interfaces.api.engagements.get_container", lambda: container)

    app = create_app()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/engagements/eng-mem-filter/memory?agent=soc")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["entries"]) == 1
        assert body["entries"][0]["source_agent"] == "soc"
        assert body["entries"][0]["content_parsed"]["summary"] == "soc finding"
