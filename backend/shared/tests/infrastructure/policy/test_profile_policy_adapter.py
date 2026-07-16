from __future__ import annotations

import pytest

from cys_core.domain.policy.product_payloads import gaia_profile_policy_payload
from cys_core.infrastructure.policy.profile_policy_adapter import (
    classify_tool_risk_for_profile,
    filter_tools_for_profile_live,
)


@pytest.mark.unit
def test_filter_tools_for_profile_live(monkeypatch) -> None:
    names = ["web_search", "run_active_scan", "browser_use"]
    filtered = filter_tools_for_profile_live(names, "gaia-benchmark")
    assert "web_search" in filtered
    assert "browser_use" in filtered


@pytest.mark.unit
def test_classify_tool_risk_for_profile_defaults(monkeypatch) -> None:
    from cys_core.domain.security.risk import classify_tool_risk
    from cys_core.domain.security.risk_level import RiskLevel

    policy = gaia_profile_policy_payload()
    assert classify_tool_risk("browser_use", policy) == RiskLevel.HIGH
    assert classify_tool_risk_for_profile("browser_use", "gaia-benchmark") in {
        RiskLevel.HIGH,
        RiskLevel.MEDIUM,
    }
