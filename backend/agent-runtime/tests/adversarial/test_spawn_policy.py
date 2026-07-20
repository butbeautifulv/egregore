from __future__ import annotations

import pytest

from bootstrap.catalog_loader import load_profile_pack
from cys_core.application.spawn_broker import SubagentSpawnBroker
from cys_core.domain.catalog.models import ProfilePack
from cys_core.domain.runs.models import InteractionMode, RunContext
from cys_core.domain.runs.spawn import SpawnWorkerPayload, sanitize_persona_overlay
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog


@pytest.mark.unit
def test_spawn_broker_rejects_plan_mode():
    catalog = InMemoryAgentCatalog()
    _, entries = load_profile_pack()
    catalog.seed(entries[:3], ProfilePack(id="t", name="t"))
    broker = SubagentSpawnBroker(catalog)
    parent = RunContext.from_session_id("s1", mode=InteractionMode.PLAN)
    payload = SpawnWorkerPayload(parent_context=parent, persona=entries[0].name, sub_goal="test")
    assert broker.validate(payload, mode=InteractionMode.PLAN) == "spawn_not_allowed_in_mode"


@pytest.mark.unit
def test_sanitize_persona_overlay_caps_length():
    text = "a" * 3000
    assert len(sanitize_persona_overlay(text)) == 2000


@pytest.mark.unit
def test_spawn_broker_rejects_max_depth():
    catalog = InMemoryAgentCatalog()
    _, entries = load_profile_pack()
    catalog.seed(entries[:3], ProfilePack(id="t", name="t"))
    # max_spawn_depth passed directly: SubagentSpawnBroker's own env-var/
    # settings fallback path only fires through a ProfilePolicyResolver
    # wired with env_overrides (real Container wiring), which this test's
    # bare InMemoryAgentCatalog + conftest's policy resolver setup doesn't
    # provide — the explicit override is the intended way to test this.
    broker = SubagentSpawnBroker(catalog, max_spawn_depth=1)
    parent = RunContext.from_session_id("s1", mode=InteractionMode.AGENT)
    parent = parent.model_copy(update={"spawn_depth": 2})
    payload = SpawnWorkerPayload(parent_context=parent, persona=entries[0].name, sub_goal="bomb")
    assert broker.validate(payload, mode=InteractionMode.AGENT) == "max_spawn_depth_exceeded"


@pytest.mark.unit
def test_spawn_broker_privilege_chain_unknown():
    catalog = InMemoryAgentCatalog()
    broker = SubagentSpawnBroker(catalog)
    parent = RunContext.one_shot_job("j1", mode=InteractionMode.AGENT)
    payload = SpawnWorkerPayload(parent_context=parent, persona="missing-agent", sub_goal="x")
    assert broker.validate(payload, mode=InteractionMode.AGENT) == "unknown_persona"
