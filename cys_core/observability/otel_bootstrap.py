from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_instrumented = False


def instrument_dependencies() -> None:
    """Auto-instrument httpx, redis, and psycopg when OTEL is enabled."""
    global _instrumented
    if _instrumented:
        return

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:
        logger.debug("httpx OTEL instrumentation unavailable", exc_info=True)

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
    except Exception:
        logger.debug("redis OTEL instrumentation unavailable", exc_info=True)

    try:
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

        PsycopgInstrumentor().instrument()
    except Exception:
        logger.debug("psycopg OTEL instrumentation unavailable", exc_info=True)

    _instrumented = True
