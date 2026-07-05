from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cys_core.domain.engagement.models import Engagement, EngagementStatus
from cys_core.domain.events.models import RoutingDecision
from interfaces.api.app import create_app
from tests.conftest import catalog_with_soc_profile, patch_catalog


class FakeStartEngagement:
    def __init__(self) -> None:
        self._goal = ""

    async def execute(self, request):
        self._goal = request.goal
        engagement = Engagement(
            id="eng-test-1",
            tenant_id=request.tenant_id,
            profile_id=request.profile_id,
            goal=request.goal,
            status=EngagementStatus.ENQUEUED,
            job_ids=["job-conductor-test"],
        )
        decision = RoutingDecision(
            event_id="eng-test-1",
            personas=["conductor"],
            playbook_id="engagement-default",
            reason="declarative",
        )
        return engagement, decision, ["job-conductor-test"]

    def get(self, engagement_id: str, *, tenant_id: str = "default"):
        if engagement_id != "eng-test-1":
            return None
        return Engagement(
            id=engagement_id,
            tenant_id=tenant_id,
            goal=self._goal or "test",
            status=EngagementStatus.ENQUEUED,
        )


@pytest.fixture
def client(monkeypatch):
    patch_catalog(monkeypatch, catalog_with_soc_profile())
    fake = FakeStartEngagement()
    monkeypatch.setattr("interfaces.api.runs._start_engagement", lambda: fake)
    return TestClient(create_app())


@pytest.mark.unit
def test_create_run_and_step(client):
    created = client.post("/runs", json={"goal": "investigate", "persona": "conductor"})
    assert created.status_code == 200
    run_id = created.json()["run_context"]["context_id"]
    assert run_id == "eng-test-1"
    assert created.json()["result"]["engagement_id"] == run_id
    stepped = client.post(f"/runs/{run_id}/steps", json={"message": "continue"})
    assert stepped.status_code == 200
    fetched = client.get(f"/runs/{run_id}")
    assert fetched.status_code == 200


@pytest.mark.unit
def test_create_session_returns_run_out(client):
    created = client.post("/sessions", json={"goal": "test session", "mode": "plan"})
    assert created.status_code == 200
    body = created.json()
    assert body["run_context"]["kind"] == "job"
    assert body["result"]["engagement_id"] == "eng-test-1"


@pytest.mark.unit
def test_approve_plan_not_available_without_legacy(client):
    created = client.post("/runs", json={"goal": "plan task", "mode": "plan"})
    assert created.status_code == 200
    run_id = created.json()["run_context"]["context_id"]
    approved = client.post(f"/runs/{run_id}/approve-plan", json={"decision": "approve"})
    assert approved.status_code == 501
