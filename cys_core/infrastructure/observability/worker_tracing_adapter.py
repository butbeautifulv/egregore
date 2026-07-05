from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from cys_core.application.ports.tracing_ports import ApplicationTracingPort, NOOP_APPLICATION_TRACING, WorkerTracingPort
from cys_core.domain.observability.models import TraceContext
from cys_core.observability.worker_spans import observability_span


class NoopApplicationTracing:
    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Any]:
        _ = name, attributes
        yield None


NOOP_APPLICATION_TRACING_IMPL: ApplicationTracingPort = NoopApplicationTracing()


class WorkerTracingAdapter:
    def __init__(self, trace_backend_getter: Callable[[], Any]) -> None:
        self._get_backend = trace_backend_getter

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Any]:
        backend = self._get_backend()
        engagement_id = (
            attributes.get("engagement_id")
            or attributes.get("investigation_id")
            or attributes.get("correlation_id")
        )
        span_attrs = dict(attributes)
        if engagement_id and "engagement_id" not in span_attrs:
            span_attrs["engagement_id"] = engagement_id
        ctx = TraceContext(span_name=name, attributes=span_attrs)
        span_id = backend.start_span(ctx)
        try:
            with observability_span(name, **attributes) as otel_span:
                yield otel_span or span_id
        finally:
            backend.end_span(span_id)


def build_application_tracing_port(trace_backend_getter: Callable[[], Any]) -> ApplicationTracingPort:
    return WorkerTracingAdapter(trace_backend_getter)


def build_worker_tracing_port(trace_backend_getter: Callable[[], Any]) -> WorkerTracingPort:
    return build_application_tracing_port(trace_backend_getter)
