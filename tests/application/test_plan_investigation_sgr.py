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
