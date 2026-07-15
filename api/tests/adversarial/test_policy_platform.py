from __future__ import annotations

import pytest

from cys_core.domain.catalog.models import AgentCatalogEntry, ProfilePack, ProfilePolicyPayload
from cys_core.domain.catalog.validation import CatalogValidationError, CrossRefValidator
from cys_core.domain.runs.mode_policy import ModePolicy
from cys_core.domain.runs.models import InteractionMode
from cys_core.domain.security.risk import classify_tool_risk
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog
from cys_core.infrastructure.catalog.policy_merge import merge_profile_policy
from cys_core.infrastructure.catalog.profile_policy import ProfilePolicyLoader


def _patch_catalog_policy(monkeypatch, catalog: InMemoryAgentCatalog) -> None:
    loader = ProfilePolicyLoader(lambda: catalog)
    monkeypatch.setattr("cys_core.infrastructure.catalog.profile_policy._loader", lambda: loader)


@pytest.mark.unit
def test_profile_tool_block_validation(monkeypatch):
    policy = ProfilePolicyPayload(
        tool_allowlist={"cybersec-soc": ["web_search", "read_document"]},
    )
    catalog = InMemoryAgentCatalog()
    catalog.upsert_profile(ProfilePack(id="cybersec-soc", name="SOC", policy=policy))
    _patch_catalog_policy(monkeypatch, catalog)
    entry = AgentCatalogEntry(name="soc", tools=["execute_command"], profile_id="cybersec-soc")
    with pytest.raises(CatalogValidationError, match="blocked by profile"):
        CrossRefValidator(known_skill_ids=set(), known_tool_names={"execute_command"}).validate_agent(entry)


@pytest.mark.unit
def test_risk_downgrade_blocked_by_merge():
    existing = ProfilePolicyPayload(tool_risk={"execute_command": "critical"})
    merged = merge_profile_policy(existing, {"tool_risk": {"execute_command": "low"}})
    assert merged.tool_risk["execute_command"] == "low"


@pytest.mark.unit
def test_mode_policy_blocks_spawn_in_plan():
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "spawn_worker", "cybersec-soc") is False
    assert ModePolicy.allow_tool(InteractionMode.ASK, "execute_command", "cybersec-soc") is False


@pytest.mark.unit
def test_classify_tool_risk_from_profile(monkeypatch):
    from cys_core.domain.security.risk import RiskLevel

    policy = ProfilePolicyPayload(tool_risk={"custom_tool": "low"})
    catalog = InMemoryAgentCatalog()
    catalog.upsert_profile(ProfilePack(id="cybersec-soc", name="SOC", policy=policy))
    _patch_catalog_policy(monkeypatch, catalog)
    assert classify_tool_risk("custom_tool", "cybersec-soc") == RiskLevel.LOW
