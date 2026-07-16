import pytest

from cys_core.domain.catalog.models import AgentCatalogEntry, CatalogSource
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.prompt_context import SECURITY_RULES_BLOCK
from cys_core.infrastructure.catalog.audit_adapter import InMemoryCatalogAudit
from cys_core.infrastructure.catalog.catalog_write_gate import CatalogWriteGate
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog
from cys_core.infrastructure.catalog.memory_mcp import InMemoryMcpServerCatalog
from cys_core.infrastructure.catalog.memory_plans import InMemoryPlanCatalog
from cys_core.infrastructure.catalog.memory_skills import InMemorySkillCatalog


@pytest.fixture
def write_gate():
    return CatalogWriteGate(
        agent_catalog=InMemoryAgentCatalog(),
        skill_catalog=InMemorySkillCatalog(),
        plan_catalog=InMemoryPlanCatalog(),
        mcp_catalog=InMemoryMcpServerCatalog(),
        audit=InMemoryCatalogAudit(),
    )


@pytest.mark.unit
def test_write_gate_strips_embedded_global_rules(write_gate):
    entry = AgentCatalogEntry(
        name="soc",
        role="worker",
        system_prompt=(
            "You are SocAgent.\n\nGLOBAL_RULES:\nmalicious\n\n"
            f"{SECURITY_RULES_BLOCK}"
        ),
        source=CatalogSource.API,
    )
    saved = write_gate.upsert_agent(entry)
    assert saved.persona_prompt == "You are SocAgent."
    assert saved.system_prompt == ""
    assert saved.system_prompt_digest
    loaded = write_gate._agents.get_agent("soc")
    assert loaded is not None
    assert "malicious" not in (loaded.persona_prompt or "")


@pytest.mark.unit
def test_write_gate_assembled_digest_not_truncated_raw(write_gate):
    entry = AgentCatalogEntry(
        name="intel",
        role="worker",
        persona_prompt="You are IntelAgent.",
        language="en",
        source=CatalogSource.API,
    )
    saved = write_gate.upsert_agent(entry)
    assert len(saved.system_prompt_digest) == 64


@pytest.mark.unit
def test_write_gate_rejects_control_persona_upsert(write_gate):
    entry = AgentCatalogEntry(name="planner", role="control", persona_prompt="mutable")

    with pytest.raises(SecurityViolation, match="Control persona 'planner' is immutable"):
        write_gate.upsert_agent(entry)


@pytest.mark.unit
def test_write_gate_rejects_control_persona_delete(write_gate):
    with pytest.raises(SecurityViolation, match="Control persona 'critic' is immutable"):
        write_gate.delete_agent("critic")
