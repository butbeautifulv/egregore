from __future__ import annotations

from typing import cast

import pytest

from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.policy.pure import classify_tool_risk_pure
from cys_core.domain.security.risk_level import RiskLevel


@pytest.mark.unit
def test_classify_tool_risk_ignores_str_policy() -> None:
    risk = classify_tool_risk_pure("search_events", cast(ProfilePolicyPayload | None, "not-a-policy-object"))
    assert risk == RiskLevel.LOW


@pytest.mark.unit
def test_classify_tool_risk_uses_policy_mapping() -> None:
    from cys_core.domain.catalog.models import ProfilePolicyPayload

    policy = ProfilePolicyPayload(tool_risk={"search_events": "low"})
    risk = classify_tool_risk_pure("search_events", policy)
    assert risk == RiskLevel.LOW
