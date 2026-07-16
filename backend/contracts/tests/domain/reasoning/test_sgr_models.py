from __future__ import annotations

import pytest
from pydantic import ValidationError

from cys_core.domain.reasoning.sgr_models import SchemaGuidedReasoningStep


@pytest.mark.unit
def test_schema_guided_reasoning_step_bounds():
    step = SchemaGuidedReasoningStep(
        reasoning_steps=["a", "b"],
        current_situation="ok",
        plan_status="planning",
        remaining_steps=["next"],
        task_completed=False,
    )
    assert len(step.reasoning_steps) == 2


@pytest.mark.unit
def test_schema_guided_reasoning_rejects_short_steps():
    with pytest.raises(ValidationError):
        SchemaGuidedReasoningStep(
            reasoning_steps=["only"],
            current_situation="x",
            plan_status="y",
            task_completed=False,
        )
