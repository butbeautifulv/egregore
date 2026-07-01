from cys_core.registry.agents import AgentRegistry
from cys_core.registry.schemas import schema_registry
from cys_core.registry.tools import tool_registry


def test_agent_registry_loads_all_agents():
    registry = AgentRegistry.load()
    names = set(registry.names())
    assert names == {"redteam", "network", "soc", "compliance", "consultant", "critic", "coordinator", "planner"}
    assert len(registry.by_workers()) == 5
    assert len(registry.by_role("specialist")) == 5
    assert registry.get("critic").role == "control"
    assert registry.get("coordinator").role == "control"
    assert registry.get("soc").role == "worker"


def test_agent_definitions_have_prompts_and_samples():
    registry = AgentRegistry.load()
    redteam = registry.get("redteam")
    assert "RedTeamAgent" in redteam.system_prompt
    assert "SYSTEM_INSTRUCTIONS:" in redteam.system_prompt
    assert "GLOBAL_RULES:" in redteam.system_prompt
    assert "SECURITY_RULES:" in redteam.system_prompt
    assert redteam.system_prompt_digest
    assert redteam.sample_input is not None
    assert "pull_request_target" in redteam.sample_input
    assert redteam.tools == [
        "read_repo_metadata",
        "parse_sast_report",
        "analyze_workflow",
        "run_active_scan",
    ]


def test_tool_registry_resolves_names():
    tools = tool_registry.resolve(["parse_netflow", "enrich_ioc"])
    assert [t.name for t in tools] == ["parse_netflow", "enrich_ioc"]
    assert "execute_command" in tool_registry.names()


def test_schema_registry_resolves_names():
    assert schema_registry.get("RedTeamFinding").__name__ == "RedTeamFinding"
    assert schema_registry.get("ConsultantFinding").__name__ == "ConsultantFinding"
    assert schema_registry.get("CriticResult").__name__ == "CriticResult"
