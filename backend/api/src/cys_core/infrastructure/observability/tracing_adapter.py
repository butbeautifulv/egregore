from __future__ import annotations

from cys_core.application.ports.tracing_ports import CorrelationIdPort
from cys_core.observability import tracing as _tracing


class CorrelationIdAdapter:
    def bind(self, correlation_id: str):
        return _tracing.bind_correlation_id(correlation_id)

    def reset(self, token) -> None:
        _tracing.reset_correlation_id(token)


def build_correlation_id_port() -> CorrelationIdPort:
    return CorrelationIdAdapter()
