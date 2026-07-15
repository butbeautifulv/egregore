from __future__ import annotations

import pytest

from cys_core.domain.runs.plan_models import WorkPlan


@pytest.mark.unit
def test_work_plan_sgr_fields():
    plan = WorkPlan(
        rationale="test",
        reasoning_steps=["a", "b"],
        plan_status="draft",
        enough_data=False,
        remaining_steps=["next"],
    )
    assert plan.reasoning_steps == ["a", "b"]
    assert plan.plan_status == "draft"
