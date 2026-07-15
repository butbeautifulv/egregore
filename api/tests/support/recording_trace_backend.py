from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from cys_core.application.ports.observability.trace_backend import TraceBackendPort
from cys_core.domain.observability.models import TraceContext


class RecordingTraceBackend:
    """In-memory TraceBackendPort for tests."""

    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, Any]]] = []

    def get_callback_handler(self) -> Any | None:
        return None

    def start_span(self, ctx: TraceContext) -> str:
        span_id = f"span-{len(self.spans)}"
        self.spans.append((ctx.span_name, dict(ctx.attributes)))
        return span_id

    def end_span(self, span_id: str) -> None:
        _ = span_id

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


class RecordingApplicationTracing:
    def __init__(self, backend: RecordingTraceBackend | None = None) -> None:
        self.backend = backend or RecordingTraceBackend()

    @contextmanager
    def span(self, name: str, **attributes: Any):
        span_id = self.backend.start_span(TraceContext(span_name=name, attributes=attributes))
        try:
            yield span_id
        finally:
            self.backend.end_span(span_id)
