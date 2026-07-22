from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.domain.workers.models import PendingHitlAction, WorkerJobStatus
from interfaces.control_plane.job_store import JobStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pending_approvals_include_correlation_id(monkeypatch):
    from interfaces.api.app import create_app

    store = JobStore()
    monkeypatch.setattr("interfaces.control_plane.job_store.get_job_store", lambda _settings=None: store)
    monkeypatch.setattr("bootstrap.container.Container.get_job_store", lambda self: store)

    store.upsert_running(
        "job-hitl",
        "worker:soc:job-hitl",
        "soc",
        correlation_id="eng-correlation-1",
        tenant_id="default",
    )
    pending = PendingHitlAction(
        job_id="job-hitl",
        session_id="worker:soc:job-hitl",
        persona="soc",
        tool_name="run_active_scan",
        tool_args={"target": "lab"},
        approval_id="appr-abc",
        risk_level="high",
    )
    store.pause_for_hitl(pending, {"params_hash": "deadbeef", "tool": "run_active_scan"})

    app = create_app(ingress=SimpleNamespace(aingest=AsyncMock()))
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        pending_list = await client.get("/approvals/pending")
        body = pending_list.json()
        assert body["count"] == 1
        assert body["approvals"][0]["correlation_id"] == "eng-correlation-1"
        assert body["approvals"][0]["job_id"] == "job-hitl"
        assert store.get("job-hitl").status == WorkerJobStatus.AWAITING_APPROVAL
