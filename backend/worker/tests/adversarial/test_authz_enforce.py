from __future__ import annotations

import pytest

from cys_core.application.spawn_broker import SubagentSpawnBroker
from cys_core.domain.runs.models import ContextKind, InteractionMode, RunContext
from cys_core.domain.runs.spawn import SpawnWorkerPayload


@pytest.mark.unit
def test_spawn_requires_workspace_in_enforce() -> None:
    from unittest.mock import MagicMock

    catalog = MagicMock()
    conductor = MagicMock()
    conductor.capabilities = ["intel"]
    agent = MagicMock()
    agent.enabled = True
    agent.profile_id = "cybersec-soc"
    agent.quality.empirical_trust = 1.0

    def get_agent(name: str):
        if name == "conductor":
            return conductor
        return agent

    catalog.get_agent.side_effect = get_agent
    broker = SubagentSpawnBroker(catalog, require_workspace_in_enforce=True)
    payload = SpawnWorkerPayload(
        parent_context=RunContext(
            context_id="ctx-1",
            kind=ContextKind.SESSION,
            tenant_id="default",
            mode=InteractionMode.AGENT,
        ),
        persona="intel",
        sub_goal="test",
    )
    reason = broker.validate(payload, mode=InteractionMode.AGENT, parent_persona="conductor", workspace_id="")
    assert reason == "workspace_required_in_enforce"
