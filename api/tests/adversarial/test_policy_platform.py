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


def _patch_catalog_policy(monkeypatch, catalog: InMemoryAgentCatalog) -> ProfilePolicyLoader:
    loader = ProfilePolicyLoader(lambda: catalog)
    monkeypatch.setattr("cys_core.infrastructure.catalog.profile_policy._loader", lambda: loader)
    return loader


def _policy_getter(loader: ProfilePolicyLoader):
    return loader.get_policy


@pytest.mark.unit
def test_profile_tool_block_validation(monkeypatch):
    policy = ProfilePolicyPayload(
        tool_allowlist={"cybersec-soc": ["web_search", "read_document"]},
    )
    catalog = InMemoryAgentCatalog()
    catalog.upsert_profile(ProfilePack(id="cybersec-soc", name="SOC", policy=policy))
    loader = _patch_catalog_policy(monkeypatch, catalog)
    entry = AgentCatalogEntry(name="soc", tools=["execute_command"], profile_id="cybersec-soc")
    with pytest.raises(CatalogValidationError, match="blocked by profile"):
        CrossRefValidator(
            known_skill_ids=set(),
            known_tool_names={"execute_command"},
            policy_getter=_policy_getter(loader),
        ).validate_agent(entry)


@pytest.mark.unit
def test_risk_downgrade_blocked_by_merge():
    existing = ProfilePolicyPayload(tool_risk={"execute_command": "critical"})
    merged = merge_profile_policy(existing, {"tool_risk": {"execute_command": "low"}})
    assert merged.tool_risk["execute_command"] == "low"


@pytest.mark.unit
def test_mode_policy_blocks_spawn_in_plan():
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "spawn_worker") is False
    assert ModePolicy.allow_tool(InteractionMode.ASK, "execute_command") is False


@pytest.mark.unit
def test_classify_tool_risk_from_profile(monkeypatch):
    from cys_core.domain.security.risk import RiskLevel

    policy = ProfilePolicyPayload(tool_risk={"custom_tool": "low"})
    catalog = InMemoryAgentCatalog()
    catalog.upsert_profile(ProfilePack(id="cybersec-soc", name="SOC", policy=policy))
    _patch_catalog_policy(monkeypatch, catalog)
    assert classify_tool_risk("custom_tool", policy) == RiskLevel.LOW
