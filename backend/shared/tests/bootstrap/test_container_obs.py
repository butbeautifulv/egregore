from __future__ import annotations

import pytest

from bootstrap.container import Container
from bootstrap.settings import get_settings
from cys_core.infrastructure.observability.backends import NoopEvalBackend, NoopTraceBackend


@pytest.mark.unit
def test_container_obs_backends(monkeypatch):
    monkeypatch.setenv("OBS_TRACE_BACKEND", "noop")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    get_settings.cache_clear()
    container = Container()
    assert isinstance(container.get_trace_backend(), NoopTraceBackend)
    assert isinstance(container.get_eval_backend(), NoopEvalBackend)
    assert container.get_prompt_resolver() is not None
