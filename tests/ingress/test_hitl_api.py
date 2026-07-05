from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.domain.workers.models import PendingHitlAction, WorkerJobStatus
from interfaces.control_plane.job_store import JobStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hitl_api_job_status_and_resume(monkeypatch):
    from interfaces.api.app import create_app

    store = JobStore()
    monkeypatch.setattr("interfaces.api.app.get_job_store", lambda: store)
    monkeypatch.setattr("interfaces.control_plane.job_store.get_job_store", lambda _settings=None: store)
    monkeypatch.setattr("interfaces.worker.hitl_resume.get_job_store", lambda: store)
    monkeypatch.setattr("bootstrap.container.Container.get_job_store", lambda self: store)

    pending = PendingHitlAction(
        job_id="job-hitl",
        session_id="worker:redteam:job-hitl",
        persona="redteam",
        tool_name="run_active_scan",
        tool_args={"target": "lab"},
        approval_id="appr-abc",
    )
    store.pause_for_hitl(pending, {"params_hash": "deadbeef", "tool": "run_active_scan"})

    monkeypatch.setattr(
        "interfaces.worker.hitl_resume.get_runtime",
        lambda: SimpleNamespace(aresume=AsyncMock(return_value={"ok": True})),
    )
    monkeypatch.setattr(
        "interfaces.worker.hitl_resume.params_hash",
        lambda _args: "deadbeef",
    )

    app = create_app(ingress=SimpleNamespace(aingest=AsyncMock()))
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        job = await client.get("/jobs/job-hitl")
        assert job.json()["status"] == WorkerJobStatus.AWAITING_APPROVAL.value

        pending_list = await client.get("/approvals/pending")
        assert pending_list.json()["count"] == 1

        resumed = await client.post(
            "/jobs/job-hitl/resume",
            json={"decision": "approve", "approval_id": "appr-abc", "actor": "alice"},
        )
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "resumed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hitl_resume_rejects_bad_approval_id(monkeypatch):
    from interfaces.api.app import create_app

    store = JobStore()
    monkeypatch.setattr("interfaces.api.app.get_job_store", lambda: store)
    monkeypatch.setattr("interfaces.control_plane.job_store.get_job_store", lambda _settings=None: store)
    monkeypatch.setattr("interfaces.worker.hitl_resume.get_job_store", lambda: store)
    monkeypatch.setattr("bootstrap.container.Container.get_job_store", lambda self: store)

    pending = PendingHitlAction(
        job_id="job-bad",
        session_id="worker:redteam:job-bad",
        persona="redteam",
        tool_name="run_active_scan",
        tool_args={"target": "lab"},
        approval_id="appr-real",
    )
    store.pause_for_hitl(pending, {"params_hash": "abc"})

    app = create_app(ingress=SimpleNamespace(aingest=AsyncMock()))
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/jobs/job-bad/resume",
            json={"decision": "approve", "approval_id": "appr-fake", "actor": "eve"},
        )
        assert resp.status_code == 400
