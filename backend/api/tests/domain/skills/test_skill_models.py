from __future__ import annotations

import pytest

from cys_core.domain.skills.models import SkillManifest, SkillTrustTier


@pytest.mark.unit
def test_skill_manifest_defaults():
    manifest = SkillManifest(skill_id="net", name="network-beaconing", description="DNS")
    assert manifest.trust_tier == SkillTrustTier.BUILTIN
    assert manifest.version == "1.0.0"
