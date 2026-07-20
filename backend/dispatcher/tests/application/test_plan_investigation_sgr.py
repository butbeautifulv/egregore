from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.planning.catalog_planner_strategy import CatalogPlannerStrategy
from tests.application.port_fakes import plan_investigation_port_kwargs


@pytest.mark.unit
def test_parse_plan_includes_reasoning_metadata():
    pi = CatalogPlannerStrategy(runtime=MagicMock(), engagement_store=MagicMock(), **plan_investigation_port_kwargs())
    plan = pi._parse_plan(
        {
            "personas": ["soc"],
            "sub_goals": {"soc": "triage"},
            "rationale": "ok",
            "reasoning_steps": ["step1", "step2"],
            "plan_status": "initial",
        },
        "goal",
    )
    assert plan.reasoning_steps == ["step1", "step2"]
    assert plan.plan_status == "initial"


@pytest.mark.unit
def test_parse_plan_loose_python_repr():
    pi = CatalogPlannerStrategy(runtime=MagicMock(), engagement_store=MagicMock(), **plan_investigation_port_kwargs())
    plan = pi._parse_plan(
        {
            "raw_response": (
                "Returning structured response: personas=['consultant'] "
                "sub_goals={'consultant': 'DevSecOps'} rationale='ok' "
                "reasoning_steps=[] plan_status='' execution_mode=None synthesis_persona=None"
            )
        },
        "Расскажи про DevSecOps",
    )
    assert plan.personas == ["consultant"]
    assert plan.sub_goals["consultant"] == "DevSecOps"


@pytest.mark.unit
def test_advisory_consultant_fallback_on_empty_personas():
    from cys_core.application.planning.post_processors import advisory_consultant_fallback
    from cys_core.domain.engagement.models import EngagementPlan

    plan = EngagementPlan(personas=[], sub_goals={}, rationale="")
    out = advisory_consultant_fallback(
        plan,
        {"advisory": True},
        ["consultant", "soc"],
        "Расскажи мне про защиту CI/CD. DevSecOps. КАК?",
    )
    assert out.personas == ["consultant"]
