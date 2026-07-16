from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.workspace.persona_resolver import resolve_worker_agent_definition
from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.workspace.models import WorkspaceAgent


@pytest.mark.unit
def test_resolve_worker_uses_platform_when_no_workspace_agent() -> None:
    platform = AgentDefinition(
        name="soc",
        description="",
        role="worker",
        system_prompt="assembled",
        persona_prompt="platform soc",
        tools=["rag_query"],
    )
    registry = MagicMock()
    registry.get.return_value = platform
    store = MagicMock()
    store.get_agent.return_value = None

    result = resolve_worker_agent_definition(
        persona="soc",
        workspace_id="ws-1",
        registry=registry,
        workspace_store=store,
    )

    assert result.persona_prompt == "platform soc"
    assert result.tools == ["rag_query"]


@pytest.mark.unit
def test_resolve_worker_overlays_workspace_agent() -> None:
    platform = AgentDefinition(
        name="soc",
        description="",
        role="worker",
        system_prompt="assembled",
        persona_prompt="platform soc",
        tools=["rag_query"],
    )
    registry = MagicMock()
    registry.get.return_value = platform
    store = MagicMock()
    store.get_agent.return_value = WorkspaceAgent(
        workspace_id="ws-1",
        name="soc",
        source_agent="soc",
        persona_prompt="workspace soc",
        tools=["investigate_incident"],
    )

    result = resolve_worker_agent_definition(
        persona="soc",
        workspace_id="ws-1",
        registry=registry,
        workspace_store=store,
    )

    assert "workspace soc" in result.system_prompt
    assert result.tools == ["investigate_incident"]
