from __future__ import annotations

from typing import Any

import structlog

from cys_core.application.engagement_bus_guard import EngagementBusGuard, GuardCounters, TripReason
from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.application.ports.job_store import JobStorePort
from cys_core.application.ports.metrics import MetricsPort
from cys_core.domain.engagement.models import EngagementStatus

logger = structlog.get_logger(__name__)


class FailEngagementGuardrail:
    """Trip engagement loop breaker: FAILED status, queue purge, egress alert."""

    def __init__(
        self,
        *,
        engagement_store: EngagementStateStore,
        job_store: JobStorePort,
        queue: JobQueueConnector | None = None,
        engagement_egress: EngagementEgressPort | None = None,
        bus_guard: EngagementBusGuard | None = None,
        metrics: MetricsPort | None = None,
    ) -> None:
        self._engagement_store = engagement_store
        self._job_store = job_store
        self._queue = queue
        self._engagement_egress = engagement_egress
        self._bus_guard = bus_guard
        self._metrics = metrics

    def execute(
        self,
        *,
        tenant_id: str,
        engagement_id: str,
        reason: TripReason,
        counters: GuardCounters | None = None,
    ) -> bool:
        if self._bus_guard is None:
            return False
        guard = self._bus_guard
        if not guard.trip(engagement_id, reason):
            return False

        self._engagement_store.fail_engagement(tenant_id, engagement_id, reason=str(reason.value))
        self._fail_pending_bus_jobs(tenant_id, engagement_id)
        self._purge_queue_jobs(engagement_id)

        counter_snapshot = counters or guard.counters(engagement_id)
        if self._metrics is not None:
            self._metrics.record_engagement_guardrail_trip(reason.value)
        logger.error(
            "engagement_guardrail_tripped",
            engagement_id=engagement_id,
            tenant_id=tenant_id,
            reason=reason.value,
            counters=counter_snapshot.__dict__,
        )

        if self._engagement_egress is not None:
            self._engagement_egress.publish_event(
                engagement_id,
                "guardrail_trip",
                {
                    "tenant_id": tenant_id,
                    "reason": reason.value,
                    "counters": counter_snapshot.__dict__,
                },
            )
        return True

    def _fail_pending_bus_jobs(self, tenant_id: str, engagement_id: str) -> None:
        for summary in self._job_store.list_by_investigation(tenant_id, engagement_id):
            if "-bus-" not in summary.job_id:
                continue
            if summary.status.value in ("pending", "running"):
                self._job_store.mark_failed(summary.job_id)

    def _purge_queue_jobs(self, engagement_id: str) -> None:
        purge = getattr(self._queue, "purge_engagement_jobs", None) if self._queue is not None else None
        if purge is None:
            return
        removed = purge(engagement_id)
        if removed:
            logger.warning("engagement_queue_purged", engagement_id=engagement_id, removed=removed)


def maybe_trip_engagement(
    *,
    tenant_id: str,
    engagement_id: str,
    engagement_store: EngagementStateStore,
    job_store: JobStorePort,
    queue: JobQueueConnector | None = None,
    engagement_egress: EngagementEgressPort | None = None,
    bus_guard: EngagementBusGuard | None = None,
    metrics: MetricsPort | None = None,
) -> TripReason | None:
    """Check guard thresholds and trip engagement if exceeded."""
    if not engagement_id or bus_guard is None:
        return None
    engagement = engagement_store.get(tenant_id, engagement_id)
    if engagement is not None and engagement.status in (EngagementStatus.CLOSED, EngagementStatus.FAILED):
        return None

    reason = bus_guard.should_trip(engagement_id)
    if reason is None:
        return None

    FailEngagementGuardrail(
        engagement_store=engagement_store,
        job_store=job_store,
        queue=queue,
        engagement_egress=engagement_egress,
        bus_guard=bus_guard,
        metrics=metrics,
    ).execute(
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        reason=reason,
        counters=bus_guard.counters(engagement_id),
    )
    return reason
