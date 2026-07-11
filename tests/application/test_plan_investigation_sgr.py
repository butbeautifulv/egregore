from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.plan_investigation import PlanInvestigation
from tests.application.port_fakes import plan_investigation_port_kwargs


@pytest.mark.unit
def test_parse_plan_includes_reasoning_metadata():
    pi = PlanInvestigation(runtime=MagicMock(), engagement_store=MagicMock(), **plan_investigation_port_kwargs())
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
    pi = PlanInvestigation(runtime=MagicMock(), engagement_store=MagicMock(), **plan_investigation_port_kwargs())
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
    pi = PlanInvestigation(runtime=MagicMock(), engagement_store=MagicMock(), **plan_investigation_port_kwargs())
    from cys_core.domain.engagement.models import EngagementPlan

    plan = EngagementPlan(personas=[], sub_goals={}, rationale="")
    out = pi._advisory_consultant_fallback(
        plan,
        "Расскажи мне про защиту CI/CD. DevSecOps. КАК?",
        ["consultant", "soc"],
    )
    assert out.personas == ["consultant"]
