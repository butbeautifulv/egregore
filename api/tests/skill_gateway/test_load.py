from __future__ import annotations

import pytest

from interfaces.gateways.skill.audit import clear_skill_audit_records, get_skill_audit_records
from interfaces.gateways.skill.load import SkillLoadError, load_skill


@pytest.mark.unit
def test_load_skill_success():
    clear_skill_audit_records()
    content = load_skill(
        "network-beaconing",
        persona="soc",
        allowed_skills=["network-beaconing"],
        job_id="job-1",
    )
    assert "BEGIN_SKILL_CONTENT" in content
    assert "SKILL_CONTENT" in content
    assert len(get_skill_audit_records()) == 1
    clear_skill_audit_records()


@pytest.mark.unit
def test_load_skill_denies_allowlist_miss():
    with pytest.raises(SkillLoadError, match="allowlist"):
        load_skill("network-beaconing", persona="soc", allowed_skills=[])
