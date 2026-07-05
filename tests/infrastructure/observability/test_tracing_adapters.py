from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.infrastructure.observability.tracing_adapter import build_correlation_id_port
from cys_core.infrastructure.observability.worker_tracing_adapter import build_worker_tracing_port


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
    port = build_worker_tracing_port()
    with port.span("worker.run", persona="soc") as span:
        assert span is sentinel


def _fake_span_ctx(value):
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        yield value

    return _ctx()
