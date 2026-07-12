from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.api.app import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.mark.unit
def test_workspace_crud_auth_disabled(client):
    created = client.post(
        "/v1/workspaces",
        json={"id": "acme-blue", "name": "Blue Team", "tenant_id": "acme"},
    )
    assert created.status_code == 200
    assert created.json()["id"] == "acme-blue"
    assert created.json()["organization_id"] == "acme"

    listed = client.get("/v1/workspaces", params={"tenant_id": "acme"})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["workspaces"]] == ["acme-blue"]

    patched = client.patch("/v1/workspaces/acme-blue", json={"name": "Blue Ops"})
    assert patched.status_code == 200
    assert patched.json()["name"] == "Blue Ops"

    deleted = client.delete("/v1/workspaces/acme-blue")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    missing = client.get("/v1/workspaces/acme-blue")
    assert missing.status_code == 404


@pytest.mark.unit
def test_workspace_agent_fork_update_and_list(client):
    client.post(
        "/v1/workspaces",
        json={"id": "default-blue", "name": "Blue Team", "tenant_id": "default"},
    )

    forked = client.post("/v1/workspaces/default-blue/agents/soc/fork")
    assert forked.status_code == 200
    assert forked.json()["name"] == "soc"
    assert forked.json()["source_agent"] == "soc"

    updated = client.put(
        "/v1/workspaces/default-blue/agents/soc",
        json={"persona_prompt": "You are workspace SOC.", "tools": ["rag_query"], "skills": []},
    )
    assert updated.status_code == 200
    assert updated.json()["persona_prompt"] == "You are workspace SOC."
    assert updated.json()["tools"] == ["rag_query"]

    listed = client.get("/v1/workspaces/default-blue/agents")
    assert listed.status_code == 200
    assert [agent["name"] for agent in listed.json()["agents"]] == ["soc"]


@pytest.mark.unit
def test_workspace_control_agent_fork_denied(client):
    client.post(
        "/v1/workspaces",
        json={"id": "default-blue", "name": "Blue Team", "tenant_id": "default"},
    )

    denied = client.post("/v1/workspaces/default-blue/agents/planner/fork")
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "CONTROL_AGENT_IMMUTABLE"


@pytest.mark.unit
def test_workspace_member_and_datasource_grants_authz_off(client):
    client.post(
        "/v1/workspaces",
        json={"id": "default-blue", "name": "Blue Team", "tenant_id": "default"},
    )

    member = client.post(
        "/v1/workspaces/default-blue/members",
        json={"user_id": "alice", "role": "viewer"},
    )
    assert member.status_code == 200
    assert member.json()["relation"] == "viewer"

    grant = client.post("/v1/workspaces/default-blue/datasources/siem/grant")
    assert grant.status_code == 200
    assert grant.json()["relation"] == "consumer"

    revoke = client.post("/v1/workspaces/default-blue/datasources/siem/revoke")
    assert revoke.status_code == 200
    assert revoke.json()["relation"] == "consumer"


@pytest.mark.unit
def test_workspace_delete_blocked_when_active_jobs(client):
    from bootstrap.container import get_container
    from cys_core.domain.engagement.models import Engagement, EngagementStatus

    client.post(
        "/v1/workspaces",
        json={"id": "busy-ws", "name": "Busy", "tenant_id": "default"},
    )
    engagement = Engagement(
        id="eng-busy",
        tenant_id="default",
        workspace_id="busy-ws",
        goal="test",
        status=EngagementStatus.RUNNING,
    )
    get_container().get_engagement_state_store().upsert(engagement)
    get_container().get_job_store().upsert_pending(
        "job-bus-eng-busy-soc",
        "soc",
        correlation_id="eng-busy",
        tenant_id="default",
    )

    denied = client.delete("/v1/workspaces/busy-ws")
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "WORKSPACE_HAS_ACTIVE_JOBS"

    get_container().get_job_store().mark_completed("job-bus-eng-busy-soc")
    deleted = client.delete("/v1/workspaces/busy-ws")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
