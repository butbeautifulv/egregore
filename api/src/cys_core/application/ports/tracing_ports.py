from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol


class CorrelationIdPort(Protocol):
    def bind(self, correlation_id: str) -> Any: ...

    def reset(self, token: Any) -> None: ...


class ApplicationTracingPort(Protocol):
    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Any]: ...


WorkerTracingPort = ApplicationTracingPort


class _NoopApplicationTracing:
    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Any]:
        _ = name, attributes
        yield None


NOOP_APPLICATION_TRACING: ApplicationTracingPort = _NoopApplicationTracing()


class TraceFlushPort(Protocol):
    def flush_traces(self) -> None: ...
