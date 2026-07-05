from __future__ import annotations

from contextlib import AbstractContextManager

from cys_core.application.ports.metrics import MetricsPort
from cys_core.observability.metrics import metrics as _metrics


class ObservabilityMetricsAdapter:
    def record_persistence_fallback(self, component: str) -> None:
        _metrics.record_persistence_fallback(component)

    def record_event_ingested(self, event_type: str) -> None:
        _metrics.record_event_ingested(event_type)

    def record_job_usage(self, persona: str, *, tokens: int, cost_usd: float) -> None:
        _metrics.record_job_usage(persona, tokens=tokens, cost_usd=cost_usd)

    def record_sgr_iron_parse_retry(self) -> None:
        _metrics.sgr_iron_parse_retries.inc()

    def set_agent_trust_score(self, persona: str, score: float) -> None:
        _metrics.set_agent_trust_score(persona, score)

    def record_memory_read(self, tenant: str, *, entries_loaded: int) -> None:
        _metrics.record_memory_read(tenant, entries_loaded=entries_loaded)

    def record_memory_write(self, tenant: str, memory_type: str) -> None:
        _metrics.record_memory_write(tenant, memory_type)

    def record_sanitizer_block(self, source: str, verdict: str) -> None:
        _metrics.record_sanitizer_block(source, verdict)

    def record_bus_dedup_dropped(self, reason: str) -> None:
        _metrics.record_bus_dedup_dropped(reason)

    def record_engagement_guardrail_trip(self, reason: str) -> None:
        _metrics.record_engagement_guardrail_trip(reason)

    def track_worker_job(self, persona: str) -> AbstractContextManager[dict[str, str]]:
        return _metrics.track_worker_job(persona)


def build_metrics_port() -> MetricsPort:
    return ObservabilityMetricsAdapter()
