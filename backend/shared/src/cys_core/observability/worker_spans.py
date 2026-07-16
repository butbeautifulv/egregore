from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from cys_core.observability.tracing import get_correlation_id

_tracer = None


def _get_tracer() -> Any | None:
    global _tracer
    if _tracer is not None:
        return _tracer
    try:
        from opentelemetry import trace

        _tracer = trace.get_tracer("egregore")
    except Exception:
        _tracer = None
    return _tracer


@contextmanager
def observability_span(name: str, **attributes: Any) -> Iterator[Any]:
    tracer = _get_tracer()
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name, attributes=attributes) as span:
        yield span


@contextmanager
def worker_job_span(
    *,
    persona: str,
    job_id: str,
    investigation_id: str = "",
    status: str = "running",
) -> Iterator[Any]:
    """Create an OTEL span for a worker job when tracing is enabled."""
    tracer = _get_tracer()
    if tracer is None:
        yield None
        return

    attributes = {
        "persona": persona,
        "job_id": job_id,
        "correlation_id": get_correlation_id() or investigation_id,
    }
    if investigation_id:
        attributes["investigation_id"] = investigation_id

    with tracer.start_as_current_span(
        "worker.process_job",
        attributes=attributes,
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.set_attribute("status", "error")
            span.record_exception(exc)
            raise
        else:
            span.set_attribute("status", status)
