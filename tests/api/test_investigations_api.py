from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.domain.memory.models import InvestigationState
from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore


def _fake_ingress() -> SimpleNamespace:
    return SimpleNamespace(aingest=AsyncMock())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_investigations(monkeypatch):
    from interfaces.api.app import create_app

    inv_store = SimpleNamespace(
        list_recent=lambda tenant_id, limit=20: [
            InvestigationState(
                investigation_id="inv-1",
                tenant_id=tenant_id,
                goal="test goal",
                status="in_progress",
                completed_personas=["soc"],
            )
        ]
    )
    monkeypatch.setattr(
        "interfaces.api.app.get_container",
        lambda: SimpleNamespace(get_investigation_state_store=lambda: inv_store),
    )

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

    state = InvestigationState(
        investigation_id="inv-2",
        tenant_id="default",
        goal="detail goal",
        status="open",
        planner_plan=["soc", "network"],
    )
    inv_store = SimpleNamespace(
        get=lambda tenant_id, investigation_id: state if investigation_id == "inv-2" else None,
        list_recent=lambda tenant_id, limit=20: [],
    )
    monkeypatch.setattr(
        "interfaces.api.app.get_container",
        lambda: SimpleNamespace(get_investigation_state_store=lambda: inv_store),
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
    monkeypatch.setattr("interfaces.api.app.get_job_store", lambda: store)
    monkeypatch.setattr(
        "interfaces.api.app.get_container",
        lambda: SimpleNamespace(
            get_investigation_state_store=lambda: SimpleNamespace(
                list_recent=lambda *a, **k: [],
                get=lambda *a, **k: None,
            )
        ),
    )

    app = create_app(ingress=_fake_ingress())
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/investigations/inv-3/jobs")
        assert resp.status_code == 200
        assert resp.json()["jobs"][0]["persona"] == "soc"
