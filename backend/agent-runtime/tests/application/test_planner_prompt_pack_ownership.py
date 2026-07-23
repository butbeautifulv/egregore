from __future__ import annotations

import pytest

from bootstrap.policy_defaults import default_profile_pack
from cys_core.application.planning.prompt_builder import CatalogPlannerPromptBuilder
from cys_core.domain.catalog.models import PlannerPack, ProfilePack


@pytest.mark.unit
def test_generic_planner_prompt_has_no_soc_assumptions() -> None:
    profile = ProfilePack(id="general", name="General")
    prompt = CatalogPlannerPromptBuilder(profile=profile, planner=PlannerPack()).build(
        goal="Summarize customer feedback",
        event_type="feedback.received",
        severity="low",
        personas=["assistant"],
        max_personas=1,
        signals={"incident_id_present": True},
    )
    assert "SIEM" not in prompt
    assert "MITRE" not in prompt
    assert "soc" not in prompt.lower()


@pytest.mark.unit
def test_cybersec_profile_keeps_its_incident_guidance() -> None:
    profile = default_profile_pack(id="cybersec-soc", default_personas=["soc", "intel"])
    prompt = CatalogPlannerPromptBuilder(profile=profile, planner=PlannerPack()).build(
        goal="Triage INC-42",
        event_type="siem.alert",
        severity="high",
        personas=["soc", "intel"],
        max_personas=2,
        signals={"incident_id_present": True},
    )
    assert "SIEM incident" in prompt
    assert "MITRE" in prompt
