from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.spawn_broker import SubagentSpawnBroker
from cys_core.domain.runs.models import InteractionMode, RunContext, ContextKind
from cys_core.domain.runs.spawn import SpawnWorkerPayload
from cys_core.domain.workspace.models import WorkspaceAgent


def _catalog_with_conductor(*, spawn_caps: list[str]):
    catalog = MagicMock()

    def get_agent(name: str):
        if name == "conductor":
            entry = MagicMock()
            entry.capabilities = spawn_caps
            return entry
        entry = MagicMock()
        entry.enabled = True
        entry.profile_id = "cybersec-soc"
        entry.quality.empirical_trust = 1.0
        return entry

    catalog.get_agent.side_effect = get_agent
    return catalog


@pytest.mark.unit
def test_spawn_denies_persona_outside_workspace_forks() -> None:
    store = MagicMock()
    store.list_agents.return_value = [
        WorkspaceAgent(workspace_id="ws-1", name="soc", source_agent="soc"),
    ]
    broker = SubagentSpawnBroker(
        _catalog_with_conductor(spawn_caps=["soc", "intel", "hunter"]),
        workspace_store=store,
        max_spawn_depth=5,
        policy_port=MagicMock(get_trust_floor=lambda _pid: 0.0),
    )
    payload = SpawnWorkerPayload(
        parent_context=RunContext(
            context_id="ctx-1",
            kind=ContextKind.SESSION,
            tenant_id="default",
            mode=InteractionMode.AGENT,
        ),
        persona="hunter",
        sub_goal="check iocs",
    )
    reason = broker.validate(
        payload,
        mode=InteractionMode.AGENT,
        parent_persona="conductor",
        workspace_id="ws-1",
    )
    assert reason == "persona_not_in_workspace"


@pytest.mark.unit
def test_spawn_allows_platform_readonly_persona_without_fork() -> None:
    store = MagicMock()
    store.list_agents.return_value = [
        WorkspaceAgent(workspace_id="ws-1", name="soc", source_agent="soc"),
    ]
    broker = SubagentSpawnBroker(
        _catalog_with_conductor(spawn_caps=["soc", "intel"]),
        workspace_store=store,
        max_spawn_depth=5,
        policy_port=MagicMock(get_trust_floor=lambda _pid: 0.0),
    )
    payload = SpawnWorkerPayload(
        parent_context=RunContext(
            context_id="ctx-1",
            kind=ContextKind.SESSION,
            tenant_id="default",
            mode=InteractionMode.AGENT,
        ),
        persona="intel",
        sub_goal="triage",
    )
    reason = broker.validate(
        payload,
        mode=InteractionMode.AGENT,
        parent_persona="conductor",
        workspace_id="ws-1",
    )
    assert reason is None


@pytest.mark.unit
def test_spawn_allows_workspace_forked_persona() -> None:
    store = MagicMock()
    store.list_agents.return_value = [
        WorkspaceAgent(workspace_id="ws-1", name="soc", source_agent="soc"),
    ]
    broker = SubagentSpawnBroker(
        _catalog_with_conductor(spawn_caps=["soc", "intel"]),
        workspace_store=store,
        max_spawn_depth=5,
        policy_port=MagicMock(get_trust_floor=lambda _pid: 0.0),
    )
    payload = SpawnWorkerPayload(
        parent_context=RunContext(
            context_id="ctx-1",
            kind=ContextKind.SESSION,
            tenant_id="default",
            mode=InteractionMode.AGENT,
        ),
        persona="soc",
        sub_goal="triage",
    )
    reason = broker.validate(
        payload,
        mode=InteractionMode.AGENT,
        parent_persona="conductor",
        workspace_id="ws-1",
    )
    assert reason is None


@pytest.mark.unit
def test_spawn_denies_non_readonly_when_workspace_has_no_forks() -> None:
    store = MagicMock()
    store.list_agents.return_value = []
    broker = SubagentSpawnBroker(
        _catalog_with_conductor(spawn_caps=["hunter", "intel"]),
        workspace_store=store,
        max_spawn_depth=5,
        policy_port=MagicMock(get_trust_floor=lambda _pid: 0.0),
    )
    payload = SpawnWorkerPayload(
        parent_context=RunContext(
            context_id="ctx-1",
            kind=ContextKind.SESSION,
            tenant_id="default",
            mode=InteractionMode.AGENT,
        ),
        persona="hunter",
        sub_goal="hunt",
    )
    reason = broker.validate(
        payload,
        mode=InteractionMode.AGENT,
        parent_persona="conductor",
        workspace_id="ws-1",
    )
    assert reason == "persona_not_in_workspace"


@pytest.mark.unit
def test_spawn_allows_workspace_forked_persona() -> None:
    store = MagicMock()
    store.list_agents.return_value = [
        WorkspaceAgent(workspace_id="ws-1", name="soc", source_agent="soc"),
    ]
    broker = SubagentSpawnBroker(
        _catalog_with_conductor(spawn_caps=["soc", "intel"]),
        workspace_store=store,
        max_spawn_depth=5,
        policy_port=MagicMock(get_trust_floor=lambda _pid: 0.0),
    )
    payload = SpawnWorkerPayload(
        parent_context=RunContext(
            context_id="ctx-1",
            kind=ContextKind.SESSION,
            tenant_id="default",
            mode=InteractionMode.AGENT,
        ),
        persona="soc",
        sub_goal="triage",
    )
    reason = broker.validate(
        payload,
        mode=InteractionMode.AGENT,
        parent_persona="conductor",
        workspace_id="ws-1",
    )
    assert reason is None


@pytest.mark.unit
def test_spawn_denies_non_readonly_when_workspace_has_no_forks() -> None:
    store = MagicMock()
    store.list_agents.return_value = []
    broker = SubagentSpawnBroker(
        _catalog_with_conductor(spawn_caps=["hunter", "intel"]),
        workspace_store=store,
        max_spawn_depth=5,
        policy_port=MagicMock(get_trust_floor=lambda _pid: 0.0),
    )
    payload = SpawnWorkerPayload(
        parent_context=RunContext(
            context_id="ctx-1",
            kind=ContextKind.SESSION,
            tenant_id="default",
            mode=InteractionMode.AGENT,
        ),
        persona="hunter",
        sub_goal="hunt",
    )
    reason = broker.validate(
        payload,
        mode=InteractionMode.AGENT,
        parent_persona="conductor",
        workspace_id="ws-1",
    )
    assert reason == "persona_not_in_workspace"
