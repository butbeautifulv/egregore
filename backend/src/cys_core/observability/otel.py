from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)
_instrumented = False
_otel_enabled_fn: Callable[[], bool] | None = None
_otel_setup: Callable[[str], None] | None = None


def _otel_enabled() -> bool:
    if _otel_enabled_fn is None:
        return False
    return _otel_enabled_fn()


def configure_otel(*, enabled: Callable[[], bool], setup: Callable[[str], None]) -> None:
    global _otel_enabled_fn, _otel_setup
    _otel_enabled_fn = enabled
    _otel_setup = setup


def setup_otel(*, service_name: str = "egregore-api") -> None:
    """Ensure OTel trace backend is initialized when enabled."""
    if not _otel_enabled():
        return
    if _otel_setup is None:
        logger.warning("OTel setup not configured")
        return
    _otel_setup(service_name)
    logger.info("OpenTelemetry trace backend initialized for %s", service_name)


def instrument_fastapi(app: Any) -> None:
    global _instrumented
    if not _otel_enabled() or _instrumented:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError as exc:
        logger.warning("FastAPI OTel instrumentation unavailable: %s", exc)
        return
    FastAPIInstrumentor.instrument_app(app)
    _instrumented = True
