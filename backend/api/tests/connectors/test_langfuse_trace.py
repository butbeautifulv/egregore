from __future__ import annotations

import pytest

from cys_core.domain.observability.models import TraceContext
from interfaces.observability.connectors.langfuse.trace import (
    LangfuseTraceBackend,
    reset_langfuse_client_cache,
)


@pytest.mark.unit
def test_langfuse_trace_noop_when_disabled(monkeypatch):
    from bootstrap.settings import get_settings, settings

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(settings, "langfuse_public_key", "")
    monkeypatch.setattr(settings, "langfuse_secret_key", "")
    monkeypatch.setattr(settings, "langfuse_api_key", "")
    reset_langfuse_client_cache()
    backend = LangfuseTraceBackend()
    ctx = TraceContext(span_name="test-span")
    assert backend.start_span(ctx) == ctx.span_name
