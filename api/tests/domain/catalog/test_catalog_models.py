from __future__ import annotations

import pytest

from cys_core.domain.catalog.models import AgentCatalogEntry, PersonaQuality, ProfilePack, SkillCatalogEntry
from cys_core.domain.catalog.validation import CatalogValidationError, CrossRefValidator
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog


@pytest.mark.unit
def test_persona_quality_serialize():
    entry = AgentCatalogEntry(name="soc", quality=PersonaQuality(empirical_trust=0.9, sample_size=3))
    data = entry.model_dump(mode="json")
    assert data["quality"]["empirical_trust"] == 0.9
    assert data["quality"]["sample_size"] == 3


@pytest.mark.unit
def test_profile_pack_policy_defaults():
    pack = ProfilePack(id="cybersec-soc", name="SOC")
    assert pack.policy.trust_floor == 0.5


@pytest.mark.unit
def test_cross_ref_validator_unknown_tool():
    entry = AgentCatalogEntry(name="soc", tools=["definitely_not_a_real_tool_xyz"])
    with pytest.raises(CatalogValidationError):
        CrossRefValidator(known_skill_ids=set(), known_tool_names=set()).validate_agent(entry)
