from cys_core.registry.agents import AgentRegistry
from cys_core.registry.schemas import schema_registry
from cys_core.registry.tools import tool_registry

WORKER_NAMES = {
    "redteam",
    "network",
    "soc",
    "compliance",
    "consultant",
    "intel",
    "hunter",
    "identity",
    "dfir",
    "cloud",
    "purple",
    "conductor",
    "research",
    "gaia_solver",
    "coding",
}

ALL_AGENT_NAMES = WORKER_NAMES | {"critic", "coordinator", "planner"}


def test_agent_registry_loads_all_agents():
    registry = AgentRegistry.load()
    names = set(registry.names())
    assert names == ALL_AGENT_NAMES
    assert len(registry.by_workers()) == len(WORKER_NAMES)
    assert len(registry.by_role("specialist")) == len(WORKER_NAMES)
    assert registry.get("critic").role == "control"
    assert registry.get("coordinator").role == "control"
    assert registry.get("soc").role == "worker"
    assert registry.get("intel").role == "worker"
    assert registry.get("purple").role == "worker"


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

    intel = registry.get("intel")
    assert "IntelAgent" in intel.system_prompt
    assert intel.schema_name == "IntelFinding"
    assert "threat-intel-osint" in intel.skills

    purple = registry.get("purple")
    assert "PurpleAgent" in purple.system_prompt
    assert purple.schema_name == "PurpleFinding"


def test_tool_registry_resolves_names():
    tools = tool_registry.resolve(["parse_netflow", "enrich_ioc"])
    assert [t.name for t in tools] == ["parse_netflow", "enrich_ioc"]
    assert "execute_command" in tool_registry.names()


def test_schema_registry_resolves_names():
    assert schema_registry.get("RedTeamFinding").__name__ == "RedTeamFinding"
    assert schema_registry.get("ConsultantFinding").__name__ == "ConsultantFinding"
    assert schema_registry.get("CriticResult").__name__ == "CriticResult"
    assert schema_registry.get("EngagementPlannerOutput").__name__ == "EngagementPlannerOutput"
    assert schema_registry.get("IntelFinding").__name__ == "IntelFinding"
    assert schema_registry.get("HunterFinding").__name__ == "HunterFinding"
    assert schema_registry.get("IdentityFinding").__name__ == "IdentityFinding"
    assert schema_registry.get("DfirFinding").__name__ == "DfirFinding"
    assert schema_registry.get("CloudFinding").__name__ == "CloudFinding"
    assert schema_registry.get("PurpleFinding").__name__ == "PurpleFinding"
