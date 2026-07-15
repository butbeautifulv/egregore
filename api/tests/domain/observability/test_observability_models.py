from __future__ import annotations

import pytest

from cys_core.domain.observability.models import (
    EvalScore,
    JudgeRequest,
    JudgeResult,
    PromptRef,
    ResolvedPrompt,
    TraceContext,
)


@pytest.mark.unit
def test_prompt_ref_and_resolved():
    ref = PromptRef(name="soc", label="production", version=2)
    resolved = ResolvedPrompt(text="body", ref=ref, source="filesystem", digest="abc")
    assert resolved.ref.name == "soc"
    assert resolved.digest == "abc"


@pytest.mark.unit
def test_trace_context_attributes():
    ctx = TraceContext(trace_id="t1", span_name="run", attributes={"k": 1})
    assert ctx.attributes["k"] == 1


@pytest.mark.unit
def test_judge_and_eval_models():
    req = JudgeRequest(
        rubric_ref=PromptRef(name="critic"),
        input_text="in",
        output_text="out",
    )
    result = JudgeResult(score=0.8, verdict="pass", reasoning="ok")
    assert result.score == 0.8
    score = EvalScore(dataset="ds", item_id="1", score=1.0, passed=True)
    assert score.passed is True
    _ = req
