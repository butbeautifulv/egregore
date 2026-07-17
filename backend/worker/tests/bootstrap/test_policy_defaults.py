from __future__ import annotations

import pytest

from bootstrap.policy_defaults import default_profile_pack, default_profile_policy
from cys_core.domain.catalog.models import ProfilePack, ProfilePolicyPayload
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.policy.defaults import default_profile_policy_payload


@pytest.mark.unit
def test_default_profile_policy_matches_domain_payload():
    assert default_profile_policy().model_dump() == default_profile_policy_payload().model_dump()


@pytest.mark.unit
def test_default_profile_policy_roundtrip():
    payload = default_profile_policy()
    restored = ProfilePolicyPayload.model_validate(payload.model_dump(mode="json"))
    assert restored.model_dump() == payload.model_dump()


@pytest.mark.unit
def test_default_profile_pack_seed_roundtrip():
    pack = default_profile_pack(id=DEFAULT_PROFILE_ID, default_personas=["soc", "network"])
    assert pack.id == DEFAULT_PROFILE_ID
    assert pack.name == "Cybersec SOC"
    assert pack.default_personas == ["soc", "network"]
    assert pack.policy.tool_allowlist is not None
    assert DEFAULT_PROFILE_ID in pack.policy.tool_allowlist

    data = pack.model_dump(mode="json")
    restored = ProfilePack.model_validate(data)
    assert restored.model_dump() == pack.model_dump()
