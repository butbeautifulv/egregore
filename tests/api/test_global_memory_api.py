from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
from cys_core.infrastructure.memory.stores import InMemoryEpisodicMemoryStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_tenant_memory_returns_cross_engagement_entries(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from interfaces.api.app import create_app

    episodic = InMemoryEpisodicMemoryStore()
    writer = MemoryWriteService(episodic)
    writer.append_finding(
        tenant_id="default",
        investigation_id="eng-a",
        source_agent="soc",
        source_job_id="job-soc-a",
        finding={"summary": "finding a"},
        trust_score=0.9,
    )
    writer.append_finding(
        tenant_id="default",
        investigation_id="eng-b",
        source_agent="hunter",
        source_job_id="job-hunter-b",
        finding={"summary": "finding b"},
        trust_score=0.8,
    )
    reader = MemoryReadService(episodic)
    monkeypatch.setattr("bootstrap.container.Container.get_memory_read_service", lambda self: reader)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/memory?tenant_id=default")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["entries"]) == 2
        investigation_ids = {e["investigation_id"] for e in body["entries"]}
        assert investigation_ids == {"eng-a", "eng-b"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_tenant_memory_filters_by_agent(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from interfaces.api.app import create_app

    episodic = InMemoryEpisodicMemoryStore()
    writer = MemoryWriteService(episodic)
    writer.append_finding(
        tenant_id="default",
        investigation_id="eng-filter",
        source_agent="soc",
        source_job_id="job-soc",
        finding={"summary": "soc only"},
        trust_score=0.9,
    )
    writer.append_finding(
        tenant_id="default",
        investigation_id="eng-filter",
        source_agent="intel",
        source_job_id="job-intel",
        finding={"summary": "intel only"},
        trust_score=0.7,
    )
    reader = MemoryReadService(episodic)
    monkeypatch.setattr("bootstrap.container.Container.get_memory_read_service", lambda self: reader)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/memory?tenant_id=default&agent=soc")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["entries"]) == 1
        assert body["entries"][0]["source_agent"] == "soc"
        assert body["entries"][0]["investigation_id"] == "eng-filter"
