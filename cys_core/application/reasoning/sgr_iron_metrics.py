from __future__ import annotations

from typing import TYPE_CHECKING

from cys_core.application.ports.metrics import MetricsPort

if TYPE_CHECKING:
    pass

_metrics_port: MetricsPort | None = None


class _NoopMetrics:
    def record_sgr_iron_parse_retry(self) -> None:
        return None


def configure_sgr_iron_metrics(port: MetricsPort | None) -> None:
    global _metrics_port
    _metrics_port = port


def _metrics() -> MetricsPort:
    return _metrics_port or _NoopMetrics()  # type: ignore[return-value]
