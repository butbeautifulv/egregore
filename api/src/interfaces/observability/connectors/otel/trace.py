from __future__ import annotations

import logging
from typing import Any

from bootstrap.settings import get_settings, settings
from cys_core.application.ports.observability.trace_backend import TraceBackendPort
from cys_core.domain.observability.models import TraceContext
from cys_core.observability.otel_bootstrap import instrument_dependencies
from cys_core.observability.otel_provider import ensure_tracer_provider, flush_tracer_provider

logger = logging.getLogger(__name__)


class OtelTraceBackend:
    """OpenTelemetry trace export (parallel sink)."""

    def __init__(self, *, service_name: str | None = None) -> None:
        self._tracer = None
        cfg = settings
        self._service_name = service_name or cfg.otel_service_name or "egregore"
        if cfg.otel_enabled:
            try:
                from opentelemetry import trace

                ensure_tracer_provider(settings=cfg, service_name=self._service_name)
                instrument_dependencies()
                self._tracer = trace.get_tracer("egregore")
            except Exception:
                logger.warning("OTel trace backend unavailable", exc_info=True)

    def get_callback_handler(self) -> Any | None:
        return None

    def start_span(self, ctx: TraceContext) -> str:
        # OTEL spans are created via observability_span in WorkerTracingAdapter.
        _ = ctx
        return ""

    def end_span(self, span_id: str) -> None:
        _ = span_id

    def flush(self) -> None:
        flush_tracer_provider()

    def shutdown(self) -> None:
        self.flush()
