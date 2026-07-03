from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import Counter, Gauge, Histogram


class CysMetrics:
    """Prometheus metrics registry for cys-agi platform signals."""

    def __init__(self) -> None:
        self.events_ingested = Counter(
            "cys_events_ingested_total",
            "Security events accepted by ingress",
            ["event_type"],
        )
        self.worker_job_duration = Histogram(
            "cys_worker_job_duration_seconds",
            "Worker job execution time",
            ["persona", "status"],
            buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
        )
        self.tool_invocations = Counter(
            "cys_tool_invocations_total",
            "MCP tool gateway invocations",
            ["tool", "result"],
        )
        self.sanitizer_blocks = Counter(
            "cys_sanitizer_blocks_total",
            "Input sanitizer blocks and filters",
            ["source", "verdict"],
        )
        self.rag_retrievals = Counter(
            "cys_rag_retrievals_total",
            "RAG retrieval attempts",
            ["tenant", "denied"],
        )
        self.agent_trust_score = Gauge(
            "cys_agent_trust_score",
            "Configured trust score per persona",
            ["persona"],
            multiprocess_mode="mostrecent",
        )
        self.job_tokens = Counter(
            "cys_job_tokens_total",
            "Estimated tokens consumed per worker job",
            ["persona"],
        )
        self.job_cost_usd = Counter(
            "cys_job_cost_usd",
            "Estimated USD cost per worker job",
            ["persona"],
        )
        self.hitl_pending = Gauge(
            "cys_hitl_pending_total",
            "Jobs awaiting human approval",
            multiprocess_mode="mostrecent",
        )
        self.approval_bypass_attempts = Counter(
            "cys_approval_bypass_attempts_total",
            "Rejected HITL resume attempts (forged approval or hash mismatch)",
            ["reason"],
        )
        self.memory_reads = Counter(
            "cys_memory_reads_total",
            "Episodic memory reads for investigation context",
            ["tenant"],
        )
        self.memory_writes = Counter(
            "cys_memory_writes_total",
            "Episodic memory writes after critic approval",
            ["tenant", "memory_type"],
        )
        self.investigations_active = Gauge(
            "cys_investigations_active",
            "Open or in-progress investigations",
            multiprocess_mode="mostrecent",
        )
        self.catalog_version = Gauge(
            "cys_catalog_version",
            "Dynamic agent catalog version",
            ["profile_id"],
            multiprocess_mode="mostrecent",
        )
        self.persistence_fallback = Counter(
            "cys_persistence_fallback_total",
            "Silent fallbacks from durable persistence to in-memory stores",
            ["component"],
        )
        self.sgr_reasoning_steps_total = Counter(
            "cys_sgr_reasoning_steps_total",
            "Schema-guided reasoning steps recorded",
        )
        self.sgr_iron_parse_retries = Counter(
            "cys_sgr_iron_parse_retries_total",
            "Iron-mode JSON parse retries",
        )

    def record_event_ingested(self, event_type: str) -> None:
        self.events_ingested.labels(event_type=event_type).inc()

    def record_tool_invocation(self, tool: str, *, success: bool) -> None:
        result = "success" if success else "error"
        self.tool_invocations.labels(tool=tool, result=result).inc()

    def record_sanitizer_block(self, source: str, verdict: str) -> None:
        self.sanitizer_blocks.labels(source=source, verdict=verdict).inc()

    def record_rag_retrieval(self, tenant: str, *, denied: bool) -> None:
        self.rag_retrievals.labels(tenant=tenant, denied="true" if denied else "false").inc()

    def set_agent_trust_score(self, persona: str, score: float) -> None:
        self.agent_trust_score.labels(persona=persona).set(score)

    def record_job_usage(self, persona: str, *, tokens: int, cost_usd: float) -> None:
        if tokens > 0:
            self.job_tokens.labels(persona=persona).inc(tokens)
        if cost_usd > 0:
            self.job_cost_usd.labels(persona=persona).inc(cost_usd)

    def refresh_hitl_pending(self, count: int) -> None:
        self.hitl_pending.set(count)

    def record_approval_bypass(self, reason: str) -> None:
        self.approval_bypass_attempts.labels(reason=reason).inc()

    def record_memory_read(self, tenant: str, *, entries_loaded: int) -> None:
        if entries_loaded > 0:
            self.memory_reads.labels(tenant=tenant).inc(entries_loaded)

    def record_memory_write(self, tenant: str, memory_type: str) -> None:
        self.memory_writes.labels(tenant=tenant, memory_type=memory_type).inc()

    def refresh_investigations_active(self, count: int) -> None:
        self.investigations_active.set(count)

    def record_persistence_fallback(self, component: str) -> None:
        self.persistence_fallback.labels(component=component).inc()

    @contextmanager
    def track_worker_job(self, persona: str) -> Iterator[dict[str, str]]:
        started = time.perf_counter()
        state = {"status": "success"}
        try:
            yield state
        except Exception:
            state["status"] = "error"
            raise
        finally:
            elapsed = time.perf_counter() - started
            self.worker_job_duration.labels(persona=persona, status=state["status"]).observe(elapsed)


metrics = CysMetrics()

_DECLARED_TRUST_BY_LEVEL = {
    "untrusted": 0.25,
    "internal": 0.75,
    "privileged": 0.9,
    "system": 1.0,
}


def declared_trust_score(entry) -> float:
    if entry.quality.sample_size > 0:
        return entry.quality.empirical_trust
    return _DECLARED_TRUST_BY_LEVEL.get(entry.trust_level, 0.5)


def seed_agent_trust_gauges() -> None:
    try:
        from cys_core.infrastructure.catalog.hybrid_registry import get_agent_catalog

        catalog = get_agent_catalog()
        for entry in catalog.list_agents(enabled_only=False):
            metrics.set_agent_trust_score(entry.name, declared_trust_score(entry))
    except Exception:
        try:
            from cys_core.registry.agents import get_agent_registry

            for defn in get_agent_registry().all():
                metrics.set_agent_trust_score(
                    defn.name, _DECLARED_TRUST_BY_LEVEL.get(defn.trust_level, 0.5)
                )
        except Exception:
            _FALLBACK_PERSONAS = {
                "conductor": 0.9,
                "consultant": 0.75,
                "analyst": 0.75,
                "responder": 0.75,
            }
            for persona, score in _FALLBACK_PERSONAS.items():
                metrics.set_agent_trust_score(persona, score)
            return
