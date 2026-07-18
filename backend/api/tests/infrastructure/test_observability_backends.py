from __future__ import annotations

import pytest

from bootstrap.observability_factory import (
    build_eval_backend,
    build_judge_backend,
    build_prompt_backend,
    build_trace_backend,
)
from cys_core.domain.observability.models import TraceContext
from cys_core.infrastructure.observability.backends import (
    NoopEvalBackend,
    NoopJudgeBackend,
    NoopPromptBackend,
    NoopTraceBackend,
)


@pytest.mark.unit
def test_noop_trace_backend():
    backend = NoopTraceBackend()
    assert backend.start_span(TraceContext(span_name="test")) == ""


@pytest.mark.unit
def test_build_backends_default_noop():
    assert isinstance(build_trace_backend("noop"), NoopTraceBackend)
    assert isinstance(build_prompt_backend("noop"), NoopPromptBackend)
    assert isinstance(build_judge_backend("noop"), NoopJudgeBackend)
    assert isinstance(build_eval_backend("noop"), NoopEvalBackend)
