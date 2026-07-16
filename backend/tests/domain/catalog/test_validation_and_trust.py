from __future__ import annotations

from types import SimpleNamespace

import pytest

from cys_core.domain.catalog.models import AgentCatalogEntry, SkillCatalogEntry, StagingStatus
from cys_core.domain.catalog.trust import declared_trust_score
from cys_core.domain.catalog.validation import CatalogValidationError, CrossRefValidator


@pytest.mark.unit
def test_declared_trust_score_prefers_empirical_quality() -> None:
    entry = SimpleNamespace(
        trust_level="internal",
        quality=SimpleNamespace(sample_size=10, empirical_trust=0.92),
    )
    assert declared_trust_score(entry) == 0.92


@pytest.mark.unit
def test_declared_trust_score_falls_back_to_trust_level() -> None:
    entry = SimpleNamespace(trust_level="privileged", quality=SimpleNamespace(sample_size=0))
    assert declared_trust_score(entry) == 0.9


@pytest.mark.unit
def test_declared_trust_score_unknown_level_defaults() -> None:
    entry = SimpleNamespace(trust_level="custom", quality=SimpleNamespace(sample_size=0))
    assert declared_trust_score(entry) == 0.5


@pytest.mark.unit
def test_cross_ref_validator_rejects_unknown_tools() -> None:
    validator = CrossRefValidator(known_tool_names={"read_file"})
    entry = AgentCatalogEntry(name="soc", tools=["read_file", "missing_tool"])
    with pytest.raises(CatalogValidationError, match="Unknown tools"):
        validator.validate_agent(entry)


@pytest.mark.unit
def test_cross_ref_validator_rejects_unknown_skills() -> None:
    validator = CrossRefValidator(known_tool_names={"read_file"}, known_skill_ids={"triage"})
    entry = AgentCatalogEntry(name="soc", tools=["read_file"], skills=["triage", "missing"])
    with pytest.raises(CatalogValidationError, match="Unknown skills"):
        validator.validate_agent(entry)


@pytest.mark.unit
def test_cross_ref_validator_skill_requires_id_and_body() -> None:
    validator = CrossRefValidator()
    with pytest.raises(CatalogValidationError, match="Skill id is required"):
        validator.validate_skill(SkillCatalogEntry(id="  ", staging_status=StagingStatus.BUILTIN))
    with pytest.raises(CatalogValidationError, match="Draft skill requires"):
        validator.validate_skill(SkillCatalogEntry(id="draft-skill", staging_status=StagingStatus.DRAFT, body=""))


@pytest.mark.unit
def test_cross_ref_validator_policy_getter_exception_is_ignored() -> None:
    def _boom(_profile_id: str) -> None:
        raise RuntimeError("policy unavailable")

    validator = CrossRefValidator(known_tool_names={"read_file"}, policy_getter=_boom)
    entry = AgentCatalogEntry(name="soc", tools=["read_file"])
    validator.validate_agent(entry)
