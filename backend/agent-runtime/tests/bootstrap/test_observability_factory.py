from __future__ import annotations

import pytest

from bootstrap.observability_factory import (
    build_eval_backend,
    build_judge_backend,
    build_prompt_backend,
    build_trace_backend,
    resolve_trace_backend_name,
)
from cys_core.infrastructure.observability.backends import (
    NoopEvalBackend,
    NoopJudgeBackend,
    NoopPromptBackend,
    NoopTraceBackend,
)


@pytest.mark.unit
def test_build_noop_backends():
    assert isinstance(build_trace_backend("noop"), NoopTraceBackend)
    assert isinstance(build_prompt_backend("noop"), NoopPromptBackend)
    assert isinstance(build_judge_backend("noop"), NoopJudgeBackend)
    assert isinstance(build_eval_backend("noop"), NoopEvalBackend)


@pytest.mark.unit
def test_resolve_trace_backend_name_composite_when_otel(monkeypatch):
    from bootstrap.settings import get_settings

    monkeypatch.setenv("OTEL_ENABLED", "1")
    monkeypatch.setenv("OBS_TRACE_BACKEND", "langfuse")
    get_settings.cache_clear()
    assert resolve_trace_backend_name() == "composite"
