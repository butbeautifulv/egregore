from __future__ import annotations

import json

import pytest

from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.infrastructure.catalog.profile_policy import ProfilePolicyLoader, _coerce_profile_policy


@pytest.mark.unit
def test_coerce_profile_policy_from_json_string() -> None:
    policy = _coerce_profile_policy(json.dumps({"tool_risk": {"search_events": "low"}}))
    assert isinstance(policy, ProfilePolicyPayload)
    assert policy.tool_risk["search_events"] == "low"


@pytest.mark.unit
def test_coerce_profile_policy_from_invalid_string() -> None:
    policy = _coerce_profile_policy("not-json")
    assert isinstance(policy, ProfilePolicyPayload)


@pytest.mark.unit
def test_profile_policy_loader_falls_back_for_missing_profile() -> None:
    from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog

    loader = ProfilePolicyLoader(lambda: InMemoryAgentCatalog())
    policy = loader.get_policy("missing-profile")
    assert isinstance(policy, ProfilePolicyPayload)
