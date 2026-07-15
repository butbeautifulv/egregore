import pytest

from cys_core.domain.catalog.models import ProfilePack
from cys_core.infrastructure.catalog.policy_merge import merge_profile_pack


@pytest.mark.unit
def test_merge_profile_pack_ignores_global_rules_patch():
    existing = ProfilePack(
        id="cybersec-soc",
        name="SOC",
        global_rules="legacy rules block",
    )
    merged = merge_profile_pack(
        existing,
        profile_id="cybersec-soc",
        body={"name": "SOC", "global_rules": "injected rules"},
    )
    assert merged.global_rules == ""
