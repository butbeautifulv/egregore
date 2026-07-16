from __future__ import annotations

from cys_core.application.ports.tracing_ports import TraceFlushPort
from cys_core.observability.langfuse_client import flush_langfuse


class TraceFlushAdapter:
    def flush_traces(self) -> None:
        flush_langfuse()


def build_trace_flush_port() -> TraceFlushPort:
    return TraceFlushAdapter()
