from __future__ import annotations

import logging

from bootstrap.observability_factory import build_trace_backend
from bootstrap.settings import get_settings
from cys_core.observability import otel as otel_module

logger = logging.getLogger(__name__)


def setup_otel_for_service(service_name: str = "egregore-api") -> None:
    from cys_core.observability.otel_provider import ensure_tracer_provider

    cfg = get_settings()
    ensure_tracer_provider(settings=cfg, service_name=service_name)
    build_trace_backend("otel", cfg=cfg, service_name=service_name)
    logger.info("OpenTelemetry trace backend initialized for %s", service_name)


def wire_otel() -> None:
    settings = get_settings()
    otel_module.configure_otel(
        enabled=lambda: settings.otel_enabled,
        setup=setup_otel_for_service,
    )
