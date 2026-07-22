from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.domain.workers.models import PendingHitlAction
from interfaces.control_plane.job_store import JobStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resume_publishes_hitl_resolved(monkeypatch):
    from interfaces.api.app import create_app

    store = JobStore()
    egress = SimpleNamespace(events=[])

    def _publish_event(engagement_id: str, event_type: str, payload: dict) -> None:
        egress.events.append((engagement_id, event_type, payload))

    egress.publish_event = _publish_event

    monkeypatch.setattr("interfaces.control_plane.job_store.get_job_store", lambda _settings=None: store)
    monkeypatch.setattr("bootstrap.container.Container.get_job_store", lambda self: store)
    monkeypatch.setattr("bootstrap.container.Container.get_engagement_egress", lambda self: egress)

    store.upsert_running(
        "job-hitl",
        "worker:soc:job-hitl",
        "soc",
        correlation_id="eng-stream-1",
        tenant_id="default",
    )
    pending = PendingHitlAction(
        job_id="job-hitl",
        session_id="worker:soc:job-hitl",
        persona="soc",
        tool_name="run_active_scan",
        tool_args={"target": "lab"},
        approval_id="appr-abc",
    )
    store.pause_for_hitl(pending, {"params_hash": "deadbeef", "tool": "run_active_scan"})

    fake_queue = SimpleNamespace(aenqueue=AsyncMock(return_value="resume-job-hitl"))
    monkeypatch.setattr("bootstrap.container.Container.get_job_queue", lambda self, persona=None: fake_queue)
    monkeypatch.setattr("interfaces.api.hitl_resume.params_hash", lambda _args: "deadbeef")

    app = create_app(ingress=SimpleNamespace(aingest=AsyncMock()))
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resumed = await client.post(
            "/jobs/job-hitl/resume",
            json={"decision": "approve", "approval_id": "appr-abc", "actor": "alice"},
        )
        assert resumed.status_code == 200

    assert any(event[1] == "hitl_resolved" for event in egress.events)
    resolved = next(event for event in egress.events if event[1] == "hitl_resolved")
    assert resolved[0] == "eng-stream-1"
    assert resolved[2]["decision"] == "approve"
