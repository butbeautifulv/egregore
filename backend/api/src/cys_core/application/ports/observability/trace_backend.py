from __future__ import annotations

from typing import Protocol

from cys_core.domain.observability.models import TraceContext


class TraceBackendPort(Protocol):
    def start_span(self, ctx: TraceContext) -> str: ...

    def end_span(self, span_id: str) -> None: ...

    def flush(self) -> None: ...

    def shutdown(self) -> None: ...
