from __future__ import annotations

import json

import pytest

from cys_core.application.reasoning.tool_instantiator import ToolInstantiator
from cys_core.domain.reasoning.sgr_models import SchemaGuidedReasoningStep


@pytest.mark.unit
def test_instantiator_happy_path():
    payload = {
        "reasoning_steps": ["step1", "step2"],
        "current_situation": "sit",
        "plan_status": "go",
        "remaining_steps": [],
        "task_completed": False,
    }
    inst = ToolInstantiator()
    parsed = inst.parse_once(json.dumps(payload), SchemaGuidedReasoningStep)
    assert parsed.task_completed is False


@pytest.mark.unit
def test_instantiator_retry_exhaustion():
    inst = ToolInstantiator()
    calls = {"n": 0}

    def bad_invoke(_prompt: str) -> str:
        calls["n"] += 1
        return "not json"

    with pytest.raises(ValueError, match="failed after"):
        inst.parse_with_retry(
            bad_invoke,
            SchemaGuidedReasoningStep,
            initial_prompt="test",
            max_retries=2,
        )
    assert calls["n"] == 2
