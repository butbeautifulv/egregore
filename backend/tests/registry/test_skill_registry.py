from __future__ import annotations

import pytest

from cys_core.registry.skill_registry import SkillRegistry, compute_skill_hash


@pytest.mark.unit
def test_skill_registry_loads_manifest_skills():
    reg = SkillRegistry.load()
    assert "network-beaconing" in reg.names()
    manifest = reg.get("network-beaconing")
    assert manifest.description
    assert len(manifest.content_hash) == 64


@pytest.mark.unit
def test_skill_metadata_block():
    reg = SkillRegistry.load()
    block = reg.metadata_block(["network-beaconing"])
    assert "network-beaconing" in block
    assert "AVAILABLE_SKILLS" in block


@pytest.mark.unit
def test_compute_skill_hash_stable():
    assert compute_skill_hash("body") == compute_skill_hash("body")
