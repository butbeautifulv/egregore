from __future__ import annotations

from cys_core.application.ports.metrics import MetricsPort

_budget_metrics: MetricsPort | None = None


class _NoopBudgetMetrics:
    def record_job_usage(self, persona: str, *, tokens: int, cost_usd: float) -> None:
        return None


def configure_budget_metrics(port: MetricsPort | None) -> None:
    global _budget_metrics
    _budget_metrics = port


def _metrics() -> MetricsPort:
    return _budget_metrics or _NoopBudgetMetrics()  # type: ignore[return-value]
