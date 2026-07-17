from __future__ import annotations

import pytest

from cys_core.application.planning.post_processors import apply_post_processors
from cys_core.domain.engagement.models import EngagementPlan, ExecutionMode


@pytest.mark.unit
def test_staged_soc_intel_post_processor() -> None:
    plan = EngagementPlan(personas=["soc"], sub_goals={"soc": "triage INC-1"})
    result = apply_post_processors(
        plan,
        ["staged_soc_intel_for_incident"],
        signals={"incident_id_present": True},
        available=["soc", "intel", "consultant"],
        goal="INC-1 malware",
    )
    assert result.personas == ["soc", "intel"]
    assert result.execution_mode == ExecutionMode.STAGED


@pytest.mark.unit
def test_advisory_consultant_fallback_processor() -> None:
    plan = EngagementPlan(personas=[], sub_goals={})
    result = apply_post_processors(
        plan,
        ["advisory_consultant_fallback"],
        signals={"advisory": True},
        available=["consultant", "soc"],
        goal="How do we harden CI/CD?",
    )
    assert result.personas == ["consultant"]
