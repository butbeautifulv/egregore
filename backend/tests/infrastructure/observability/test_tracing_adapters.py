from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.infrastructure.observability.tracing_adapter import build_correlation_id_port
from cys_core.infrastructure.observability.worker_tracing_adapter import build_worker_tracing_port
from cys_core.observability import tracing


@pytest.mark.unit
def test_inject_correlation_headers_normalizes_wrapped_id():
    wrapped = (
        'USER_DATA_TO_PROCESS [source=agent_bus]:\n'
        '<untrusted_data source="agent_bus">\n'
        "eng-cafebabef00d\n"
        "</untrusted_data>"
    )
    token = tracing.bind_correlation_id(wrapped)
    try:
        headers = tracing.inject_correlation_headers({})
        assert headers.get("x-correlation-id") == "eng-cafebabef00d"
    finally:
        tracing.reset_correlation_id(token)


@pytest.mark.unit
def test_inject_correlation_headers_omits_unsafe_newlines():
    token = tracing.bind_correlation_id("bad\nid")
    try:
        headers = tracing.inject_correlation_headers({})
        assert "x-correlation-id" not in headers
    finally:
        tracing.reset_correlation_id(token)


@pytest.mark.unit
def test_correlation_id_adapter_delegates_bind_reset(monkeypatch):
    bind = MagicMock(return_value="token-1")
    reset = MagicMock()
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.tracing_adapter._tracing.bind_correlation_id",
        bind,
    )
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.tracing_adapter._tracing.reset_correlation_id",
        reset,
    )
    port = build_correlation_id_port()
    token = port.bind("corr-1")
    port.reset(token)
    bind.assert_called_once_with("corr-1")
    reset.assert_called_once_with("token-1")


@pytest.mark.unit
def test_worker_tracing_adapter_yields_span(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        "cys_core.infrastructure.observability.worker_tracing_adapter.observability_span",
        lambda name, **attrs: _fake_span_ctx(sentinel),
    )
    backend = MagicMock()
    backend.start_span.return_value = "span-1"
    port = build_worker_tracing_port(lambda: backend)
    with port.span("worker.run", persona="soc") as span:
        assert span is sentinel


def _fake_span_ctx(value):
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        yield value

    return _ctx()
