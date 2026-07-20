from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

_trace_backend_factory: Callable[[], Any] | None = None


def configure_trace_backend_factory(factory: Callable[[], Any]) -> None:
    global _trace_backend_factory
    _trace_backend_factory = factory


@lru_cache
def _trace_backend():
    if _trace_backend_factory is None:
        from cys_core.infrastructure.observability.backends import NoopTraceBackend

        return NoopTraceBackend()
    return _trace_backend_factory()


def get_langfuse_callback_handler() -> Any | None:
    """Thin shim — delegates to TraceBackendPort."""
    return _trace_backend().get_callback_handler()


def flush_langfuse() -> None:
    _trace_backend().flush()


def shutdown_langfuse() -> None:
    _trace_backend().shutdown()


def reset_langfuse_client_cache() -> None:
    """Clear cached backend (tests only)."""
    _trace_backend.cache_clear()
