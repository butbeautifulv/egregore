from __future__ import annotations

import pytest

from cys_core.domain.policy.product_payloads import profile_policy_for


@pytest.mark.unit
def test_gaia_profile_has_sgr_hybrid_overlay() -> None:
    policy = profile_policy_for("gaia-benchmark")
    assert policy.sgr.enabled is True
    assert policy.sgr.mode == "sgr_hybrid"
    assert policy.tool_allowlist["gaia-benchmark"] is not None


@pytest.mark.unit
def test_cybersec_profile_keeps_open_tool_allowlist() -> None:
    policy = profile_policy_for("cybersec-soc")
    assert policy.tool_allowlist.get("cybersec-soc") is None
