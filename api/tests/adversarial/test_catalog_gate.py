from __future__ import annotations

import pytest

from cys_core.domain.catalog.models import SkillCatalogEntry, StagingStatus
from cys_core.infrastructure.catalog.memory_skills import InMemorySkillCatalog


@pytest.mark.unit
def test_draft_skill_blocked_on_load(monkeypatch):
    from interfaces.gateways.skill.load import SkillLoadError, load_skill

    catalog = InMemorySkillCatalog()
    catalog.upsert_skill(
        SkillCatalogEntry(
            id="blocked-skill",
            body="# blocked",
            staging_status=StagingStatus.DRAFT,
        )
    )
    monkeypatch.setattr("interfaces.gateways.skill.load.get_use_dynamic_catalog", lambda: True)
    monkeypatch.setattr("interfaces.gateways.skill.load.get_skill_catalog", lambda: catalog)
    with pytest.raises(SkillLoadError, match="draft"):
        load_skill("blocked-skill", persona="soc", allowed_skills=["blocked-skill"])
