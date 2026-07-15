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
            buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 420, 600),
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
        self.immutable_rules_version = Gauge(
            "cys_immutable_rules_version",
            "Immutable prompt rules bundle active (1 = current)",
            ["version"],
            multiprocess_mode="mostrecent",
        )
        self.persistence_fallback = Counter(
            "cys_persistence_fallback_total",
            "Silent fallbacks from durable persistence to in-memory stores",
            ["component"],
        )
        self.infrastructure_fallback = Counter(
            "cys_infrastructure_fallback_total",
            "Fallbacks from durable infrastructure adapters to in-memory paths",
            ["component", "reason"],
        )
        self.sgr_reasoning_steps_total = Counter(
            "cys_sgr_reasoning_steps_total",
            "Schema-guided reasoning steps recorded",
        )
        self.sgr_iron_parse_retries = Counter(
            "cys_sgr_iron_parse_retries_total",
            "Iron-mode JSON parse retries",
        )
        self.bus_dedup_dropped = Counter(
            "cys_bus_dedup_dropped_total",
            "Bus ingress envelopes dropped by dedup layer",
            ["reason"],
        )
        self.engagement_guardrail_trip = Counter(
            "cys_engagement_guardrail_trip_total",
            "Engagement bus loop guardrail trips",
            ["reason"],
        )
        self.skill_loads = Counter(
            "cys_skill_loads_total",
            "Skills loaded by workers via load_skill",
            ["skill", "persona"],
        )
        self.worker_job_timeouts = Counter(
            "cys_worker_job_timeout_total",
            "Worker jobs that hit wall-clock timeout without salvage",
            ["persona"],
        )
        self.worker_job_failures = Counter(
            "cys_worker_job_failures_total",
            "Terminal worker job failures by reason",
            ["persona", "reason"],
        )
        self.worker_job_salvaged = Counter(
            "cys_worker_job_salvaged_total",
            "Worker jobs salvaged with partial findings",
            ["persona", "reason"],
        )
        self.bus_enqueue_rejected_off_plan = Counter(
            "cys_bus_enqueue_rejected_off_plan_total",
            "Bus enqueue rejected because recipient is outside planner_plan",
            ["reason"],
        )
        self.bus_revision_rejected = Counter(
            "cys_bus_revision_rejected_total",
            "Bus revision enqueue rejected (revision cap or guard)",
            ["reason"],
        )
        self.planner_stuck_fallback = Counter(
            "cys_planner_stuck_fallback_total",
            "Engagements recovered with fallback plan after async planner timeout",
        )
        self.catalog_drift = Gauge(
            "cys_catalog_drift",
            "Catalog drift detected at startup (1=drift, 0=ok)",
            ["agent", "field"],
        )
        self.follow_up_queued = Counter(
            "cys_follow_up_queued_total",
            "Operator follow-up jobs enqueued",
            ["work_kind"],
        )
        self.follow_up_completed = Counter(
            "cys_follow_up_completed_total",
            "Operator follow-up jobs completed successfully",
            ["work_kind"],
        )
        self.follow_up_failed = Counter(
            "cys_follow_up_failed_total",
            "Operator follow-up jobs failed",
            ["work_kind"],
        )
        self.work_orders_created = Counter(
            "cys_work_orders_created_total",
            "Work orders created",
            ["profile_id"],
        )
        self.authz_check_total = Counter(
            "cys_authz_check_total",
            "Authorization checks by decision, relation, and object type",
            ["decision", "relation", "object_type"],
        )
        self.authz_deny_total = Counter(
            "cys_authz_deny_total",
            "Authorization denials by relation and object type",
            ["relation", "object_type"],
        )
        self.authz_error_total = Counter(
            "cys_authz_error_total",
            "Authorization check errors by relation and object type",
            ["relation", "object_type"],
        )
        self.authz_check_latency = Histogram(
            "cys_authz_check_latency_seconds",
            "Authorization check latency",
            ["relation"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
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

    def record_infrastructure_fallback(self, component: str, *, reason: str) -> None:
        self.infrastructure_fallback.labels(component=component, reason=reason).inc()

    def record_bus_dedup_dropped(self, reason: str) -> None:
        self.bus_dedup_dropped.labels(reason=reason).inc()

    def record_engagement_guardrail_trip(self, reason: str) -> None:
        self.engagement_guardrail_trip.labels(reason=reason).inc()

    def record_skill_load(self, skill_name: str, persona: str) -> None:
        self.skill_loads.labels(skill=skill_name, persona=persona).inc()

    def record_worker_job_timeout(self, persona: str) -> None:
        self.worker_job_timeouts.labels(persona=persona).inc()

    def record_worker_job_failure(self, persona: str, reason: str) -> None:
        self.worker_job_failures.labels(persona=persona, reason=reason).inc()

    def record_worker_job_salvaged(self, persona: str, reason: str) -> None:
        self.worker_job_salvaged.labels(persona=persona, reason=reason).inc()

    def record_bus_enqueue_rejected_off_plan(self, reason: str) -> None:
        self.bus_enqueue_rejected_off_plan.labels(reason=reason).inc()

    def record_bus_revision_rejected(self, reason: str) -> None:
        self.bus_revision_rejected.labels(reason=reason).inc()

    def record_planner_stuck_fallback(self) -> None:
        self.planner_stuck_fallback.inc()

    def set_catalog_drift(self, agent: str, field: str, *, drift: bool) -> None:
        self.catalog_drift.labels(agent=agent, field=field).set(1.0 if drift else 0.0)

    def record_follow_up_queued(self, work_kind: str) -> None:
        self.follow_up_queued.labels(work_kind=work_kind or "unknown").inc()

    def record_follow_up_completed(self, work_kind: str) -> None:
        self.follow_up_completed.labels(work_kind=work_kind or "unknown").inc()

    def record_follow_up_failed(self, work_kind: str) -> None:
        self.follow_up_failed.labels(work_kind=work_kind or "unknown").inc()

    def record_work_order_created(self, profile_id: str) -> None:
        self.work_orders_created.labels(profile_id=profile_id or "unknown").inc()

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

from cys_core.domain.catalog.trust import declared_trust_score as _declared_trust_score  # noqa: E402


def declared_trust_score(entry) -> float:
    return _declared_trust_score(entry)


def seed_immutable_rules_version() -> None:
    from cys_core.domain.security.immutable_rules import IMMUTABLE_RULES_VERSION

    metrics.immutable_rules_version.labels(version=IMMUTABLE_RULES_VERSION).set(1)


def seed_agent_trust_gauges() -> None:
    seed_immutable_rules_version()
    try:
        from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog

        catalog = get_agent_catalog()
        for entry in catalog.list_agents(enabled_only=False):
            metrics.set_agent_trust_score(entry.name, declared_trust_score(entry))
    except Exception:
        try:
            from cys_core.registry.agents import get_agent_registry

            for defn in get_agent_registry().all():
                metrics.set_agent_trust_score(defn.name, declared_trust_score(defn))
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
