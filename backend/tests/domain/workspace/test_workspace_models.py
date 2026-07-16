from __future__ import annotations

import pytest

from cys_core.domain.workspace.models import Workspace, WorkspaceAgent


@pytest.mark.unit
def test_workspace_defaults() -> None:
    ws = Workspace(id="ws-1", name="SOC desk")
    assert ws.organization_id == "default"
    assert ws.profile_id == "cybersec-soc"
    assert ws.soft_deleted is False
    assert ws.created_at.tzinfo is not None


@pytest.mark.unit
def test_workspace_agent_fork_fields() -> None:
    agent = WorkspaceAgent(
        workspace_id="ws-1",
        name="soc-local",
        source_agent="soc",
        persona_prompt="You are SOC.",
        tools=["siem_search"],
        skills=["triage"],
    )
    assert agent.language == "ru"
    assert agent.tools == ["siem_search"]
    assert agent.skills == ["triage"]
    assert agent.updated_at.tzinfo is not None
