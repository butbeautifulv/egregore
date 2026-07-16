from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from bootstrap.settings import get_settings
from cys_core.observability.tracing import get_correlation_id

_configured = False


def _add_correlation_id(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def _add_otel_context(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
    except Exception:
        return event_dict
    return event_dict


def configure_logging(service_name: str, *, stream: Any = None) -> None:
    """Configure structlog JSON logging for stdout (Loki/Promtail ingestion).

    ``stream`` defaults to stdout for every long-running service (serve,
    worker daemon, coordinator/critic daemons) where a container runtime
    scrapes stdout for logs. ``run-sandboxed-job`` is the one caller that
    passes stderr instead: its stdout is the SubprocessExecutionBackend IPC
    channel (a single final RunResult JSON line) and must not be interleaved
    with per-event log lines."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_correlation_id,
        _add_otel_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service_name)

    _configured = True
