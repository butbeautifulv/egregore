from __future__ import annotations

import pytest

from bootstrap.catalog_loader import load_profile_pack
from cys_core.domain.policy.product_payloads import gaia_profile_policy_payload
from cys_core.domain.security.profile_tools import filter_tools_for_profile


@pytest.mark.unit
def test_filter_tools_gaia_bench_blocks_soc_tools():
    policy = gaia_profile_policy_payload()
    blocked = filter_tools_for_profile(
        ["execute_command", "web_search"],
        "gaia-benchmark",
        policy=policy,
    )
    assert blocked == ["web_search"]


@pytest.mark.unit
def test_filter_tools_cybersec_soc_allows_all():
    tools = ["execute_command", "query_siem_readonly", "spawn_worker"]
    assert filter_tools_for_profile(tools, "cybersec-soc") == tools


@pytest.mark.unit
def test_catalog_loader_returns_profile_and_agents():
    profile, entries = load_profile_pack()
    assert profile.id == "cybersec-soc"
    assert profile.policy.tool_allowlist
    assert len(entries) > 0
    assert entries[0].name
    planner = next(entry for entry in entries if entry.name == "planner")
    assert planner.output_schema == "EngagementPlannerOutput"
