from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.api.app import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.mark.unit
def test_catalog_list_and_profiles(client):
    listed = client.get("/catalog/agents")
    assert listed.status_code == 200
    assert "agents" in listed.json()
    profiles = client.get("/catalog/profiles")
    assert profiles.status_code == 200
    assert "profiles" in profiles.json()


@pytest.mark.unit
def test_catalog_put_stripped_prompt_still_has_security_rules(client):
    put = client.put(
        "/catalog/agents/test-agent-rules",
        json={
            "description": "demo",
            "role": "worker",
            "system_prompt": "You are TestAgent.",
            "tools": [],
            "skills": [],
        },
    )
    assert put.status_code == 200
    got = client.get("/catalog/agents/test-agent-rules")
    assert got.status_code == 200
    body = got.json()
    assert "SECURITY_RULES:" in body["system_prompt"]
    assert "GLOBAL_RULES:" in body["system_prompt"]
    assert body["persona_prompt"] == "You are TestAgent."


@pytest.mark.unit
def test_catalog_put_and_audit(client):
    put = client.put(
        "/catalog/agents/test-agent",
        json={"description": "demo", "role": "worker", "tools": [], "skills": []},
    )
    assert put.status_code == 200
    assert put.json()["name"] == "test-agent"
    got = client.get("/catalog/agents/test-agent")
    assert got.status_code == 200
    audit = client.get("/catalog/audit")
    assert audit.status_code == 200


@pytest.mark.unit
def test_catalog_control_persona_mutation_denied(client):
    put = client.put(
        "/catalog/agents/planner",
        json={"description": "demo", "role": "control", "tools": [], "skills": []},
    )
    assert put.status_code == 403
    assert put.json()["detail"]["code"] == "CONTROL_AGENT_IMMUTABLE"

    delete = client.delete("/catalog/agents/critic")
    assert delete.status_code == 403
    assert delete.json()["detail"]["code"] == "CONTROL_AGENT_IMMUTABLE"


@pytest.mark.unit
def test_catalog_list_includes_hitl_auto_approve(client):
    listed = client.get("/catalog/agents")
    assert listed.status_code == 200
    agents = listed.json()["agents"]
    assert agents
    assert "hitl_auto_approve" in agents[0]


@pytest.mark.unit
def test_catalog_put_hitl_auto_approve_round_trip(client):
    put = client.put(
        "/catalog/agents/test-hitl-auto",
        json={
            "description": "demo",
            "role": "worker",
            "tools": [],
            "skills": [],
            "hitl_auto_approve": True,
        },
    )
    assert put.status_code == 200
    assert put.json()["hitl_auto_approve"] is True
    got = client.get("/catalog/agents/test-hitl-auto")
    assert got.status_code == 200
    assert got.json()["hitl_auto_approve"] is True


@pytest.mark.unit
def test_catalog_seed(client):
    seeded = client.post("/catalog/seed")
    assert seeded.status_code == 200
    assert seeded.json()["seeded"] >= 0
