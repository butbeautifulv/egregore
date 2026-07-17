import pytest

from cys_core.application.use_cases.suggest_persona_patch import SuggestPersonaPatch
from cys_core.domain.security.prompt_context import SECURITY_RULES_BLOCK
from cys_core.infrastructure.catalog.audit_adapter import InMemoryCatalogAudit
from cys_core.infrastructure.catalog.catalog_write_gate import CatalogWriteGate
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog
from cys_core.infrastructure.catalog.memory_mcp import InMemoryMcpServerCatalog
from cys_core.infrastructure.catalog.memory_plans import InMemoryPlanCatalog
from cys_core.infrastructure.catalog.memory_skills import InMemorySkillCatalog
from cys_core.infrastructure.catalog.memory_tools import InMemoryToolCatalog


@pytest.mark.unit
def test_suggest_persona_patch_routes_through_write_gate():
    agents = InMemoryAgentCatalog()
    gate = CatalogWriteGate(
        agent_catalog=agents,
        skill_catalog=InMemorySkillCatalog(),
        plan_catalog=InMemoryPlanCatalog(),
        mcp_catalog=InMemoryMcpServerCatalog(),
        tool_catalog=InMemoryToolCatalog(),
        audit=InMemoryCatalogAudit(),
    )
    use_case = SuggestPersonaPatch(agents, write_gate=gate)
    saved = use_case.execute(
        "soc",
        description="draft",
        system_prompt=f"You are SocAgent.\n\nGLOBAL_RULES:\nfake\n\n{SECURITY_RULES_BLOCK}",
    )
    assert saved.name == "soc-draft"
    assert saved.persona_prompt == "You are SocAgent."
    assert "fake" not in saved.persona_prompt
