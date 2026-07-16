from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus
from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore


def _fake_ingress() -> SimpleNamespace:
    return SimpleNamespace(aingest=AsyncMock())


def _patch_container(monkeypatch, container: SimpleNamespace) -> None:
    import bootstrap.container as container_mod
    from bootstrap.settings import get_settings
    from cys_core.application.authz.service import AuthzService
    from cys_core.infrastructure.authz.noop import NoopAuthzPort

    if not hasattr(container, "get_job_store"):
        container.get_job_store = lambda: InMemoryJobStore()
    if not hasattr(container, "settings"):
        container.settings = get_settings()
    if not hasattr(container, "get_agent_catalog"):
        catalog = MagicMock()
        catalog.bus_recipients = []
        container.get_agent_catalog = lambda: catalog
    if not hasattr(container, "get_authz_service"):
        container.get_authz_service = lambda: AuthzService(NoopAuthzPort(), mode="off")
    container_mod._container = container
    monkeypatch.setattr("bootstrap.container.get_container", lambda: container)
    monkeypatch.setattr("interfaces.api.app.get_container", lambda: container)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_investigations(monkeypatch):
    from interfaces.api.app import create_app

    engagement = Engagement(
        id="inv-1",
        tenant_id="default",
        goal="test goal",
        status=EngagementStatus.RUNNING,
        mode=EngagementMode.ASYNC,
        completed_personas=["soc"],
    )
    eng_store = SimpleNamespace(
        list_recent_page=lambda tenant_id, limit=20, cursor=None: (
            [(engagement, datetime.now(UTC))],
            None,
        ),
    )
    _patch_container(monkeypatch, SimpleNamespace(get_engagement_state_store=lambda: eng_store))

    app = create_app(ingress=_fake_ingress())
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/investigations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["investigations"][0]["investigation_id"] == "inv-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_investigation_detail(monkeypatch):
    from interfaces.api.app import create_app

    engagement = Engagement(
        id="inv-2",
        tenant_id="default",
        goal="detail goal",
        status=EngagementStatus.PLANNING,
        mode=EngagementMode.ASYNC,
        planner_plan=["soc", "network"],
    )
    eng_store = SimpleNamespace(
        get=lambda tenant_id, investigation_id: engagement if investigation_id == "inv-2" else None,
        list_recent=lambda tenant_id, limit=20: [],
    )
    egress = SimpleNamespace(snapshot=lambda *_a, **_k: [])
    _patch_container(
        monkeypatch,
        SimpleNamespace(
            get_engagement_state_store=lambda: eng_store,
            get_engagement_egress=lambda: egress,
        ),
    )

    app = create_app(ingress=_fake_ingress())
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/investigations/inv-2")
        assert resp.status_code == 200
        assert resp.json()["planner_plan"] == ["soc", "network"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_investigation_jobs(monkeypatch):
    from interfaces.api.app import create_app

    store = InMemoryJobStore()
    store.upsert_running("job-a", "sess-a", "soc", correlation_id="inv-3", tenant_id="default", event_id="evt-3")
    _patch_container(
        monkeypatch,
        SimpleNamespace(
            get_engagement_state_store=lambda: SimpleNamespace(
                list_recent=lambda *a, **k: [],
                get=lambda *a, **k: None,
            ),
            get_job_store=lambda: store,
        ),
    )

    app = create_app(ingress=_fake_ingress())
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/investigations/inv-3/jobs")
        assert resp.status_code == 200
        assert resp.json()["jobs"][0]["persona"] == "soc"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_investigation_preserves_closed_status_with_egress(monkeypatch):
    from interfaces.api.app import create_app

    engagement = Engagement(
        id="inv-closed",
        tenant_id="default",
        goal="done goal",
        status=EngagementStatus.CLOSED,
        mode=EngagementMode.ASYNC,
        completed_personas=["consultant"],
        planner_plan=["consultant"],
    )
    eng_store = SimpleNamespace(
        get=lambda tenant_id, investigation_id: engagement if investigation_id == "inv-closed" else None,
        list_recent=lambda tenant_id, limit=20: [],
    )
    egress = SimpleNamespace(
        snapshot=lambda *_a, **_k: [{"phase": "job_finished", "payload": {"persona": "consultant"}}],
    )
    _patch_container(
        monkeypatch,
        SimpleNamespace(
            get_engagement_state_store=lambda: eng_store,
            get_engagement_egress=lambda: egress,
        ),
    )

    app = create_app(ingress=_fake_ingress())
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/investigations/inv-closed")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "closed"
        assert body["latest_phase"] == "job_finished"
