from __future__ import annotations

import logging
from typing import Any

from bootstrap.settings import get_settings

logger = logging.getLogger(__name__)
_configured = False


def setup_otel(*, service_name: str = "egregore-api") -> None:
    """Configure OTLP trace export when OTEL_ENABLED=true."""
    global _configured
    settings = get_settings()
    if not settings.otel_enabled or _configured:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning("OpenTelemetry packages missing; tracing disabled: %s", exc)
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_endpoint,
        insecure=True,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _configured = True
    logger.info("OpenTelemetry tracing enabled → %s", settings.otel_exporter_endpoint)


def instrument_fastapi(app: Any) -> None:
    if not get_settings().otel_enabled:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError as exc:
        logger.warning("FastAPI OTel instrumentation unavailable: %s", exc)
        return
    FastAPIInstrumentor.instrument_app(app)
