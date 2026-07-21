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


@pytest.mark.unit
def test_general_assistant_profile_has_datasource_allowlist() -> None:
    policy = profile_policy_for("general-assistant")
    assert policy.datasource_allowlist == {"general-assistant": ["web-cache", "docs-index"]}


@pytest.mark.unit
def test_cybersec_profile_keeps_its_mode_policy_and_escalation_paths() -> None:
    """Regression guard for the §8.4 point 3 gating fix below: cybersec-soc's own behavior
    must not change — it still gets the full SOC read_only/plan_blocked/mutating tool
    lists and soc/redteam-shaped escalation pairs."""
    policy = profile_policy_for("cybersec-soc")
    assert policy.mode_policy.read_only_tools
    assert ("soc", "redteam") in {tuple(pair) for pair in policy.escalation_paths}


@pytest.mark.unit
def test_non_soc_profiles_do_not_inherit_cybersec_soc_mode_policy_or_escalation_paths() -> None:
    """docs/MSP_BACKLOG.md §8.2/§8.4 point 3: a non-SOC profile pack used to silently
    inherit cybersec-soc's SIEM/threat-intel read_only_tools and soc/redteam escalation
    pairs from this same function — exactly the "core stays SOC-shaped even for a non-SOC
    pack" gap. Both profiles below must now get empty defaults instead."""
    for profile_id in ("general-assistant", "gaia-benchmark"):
        policy = profile_policy_for(profile_id)
        assert policy.mode_policy.read_only_tools == []
        assert policy.mode_policy.plan_blocked_tools == []
        assert policy.escalation_paths == []
