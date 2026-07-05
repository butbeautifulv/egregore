from __future__ import annotations

import uuid
from typing import Any

import structlog

from cys_core.application.bus_engagement import extract_engagement_id
from cys_core.application.engagement_bus_guard import EngagementBusGuard, get_engagement_bus_guard
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.application.ports.job_store import JobStorePort
from cys_core.application.ports.metrics import MetricsPort
from cys_core.application.workers.noop_finding import is_noop_finding
from cys_core.application.use_cases.fail_engagement_guardrail import maybe_trip_engagement
from cys_core.domain.engagement.models import EngagementStatus
from cys_core.domain.workers.job_factory import jobs_for_routing
from cys_core.domain.workers.models import WorkerJob

logger = structlog.get_logger(__name__)


class EnqueueWorkerJobs:
    """Create worker jobs, persist pending state, and enqueue for execution."""

    def __init__(
        self,
        *,
        queue: JobQueueConnector,
        job_store: JobStorePort,
        engagement_store: EngagementStateStore | None = None,
        bus_guard: EngagementBusGuard | None = None,
        metrics: MetricsPort | None = None,
        max_jobs_per_engagement: int = 20,
    ) -> None:
        self._queue = queue
        self._job_store = job_store
        self._engagement_store = engagement_store
        self._bus_guard = bus_guard
        self._metrics = metrics
        self._max_jobs_per_engagement = max_jobs_per_engagement

    def _log_queue_depth(self, *, job_ids: list[str], correlation_id: str) -> None:
        depth_fn = getattr(self._queue, "queue_depth", None)
        if depth_fn is None:
            return
        depth = depth_fn()
        if depth is None:
            return
        logger.info(
            "worker_jobs_enqueued",
            job_ids=job_ids,
            correlation_id=correlation_id,
            queue_depth=depth,
            queue_backend=getattr(self._queue, "active_backend", self._queue.name),
        )

    def _enqueue_to_queue(self, job: WorkerJob, *, pipeline_staged: bool, index: int) -> None:
        if pipeline_staged and index == 0:
            enqueue_front = getattr(self._queue, "enqueue_front", None)
            if enqueue_front is not None:
                enqueue_front(job)
                return
        self._queue.enqueue(job)

    async def _aenqueue_to_queue(self, job: WorkerJob, *, pipeline_staged: bool, index: int) -> None:
        if pipeline_staged and index == 0:
            enqueue_front = getattr(self._queue, "aenqueue_front", None)
            if enqueue_front is not None:
                await enqueue_front(job)
                return
        await self._queue.aenqueue(job)

    def _persist_and_enqueue_jobs(
        self,
        jobs: list[WorkerJob],
        *,
        pipeline_staged: bool = False,
    ) -> list[str]:
        job_ids: list[str] = []
        for index, job in enumerate(jobs):
            self._job_store.upsert_pending(
                job.job_id,
                job.persona,
                correlation_id=job.correlation_id,
                tenant_id=job.tenant_id,
                event_id=job.event_id,
            )
            if not pipeline_staged or index == 0:
                self._enqueue_to_queue(job, pipeline_staged=pipeline_staged, index=index)
            job_ids.append(job.job_id)
        if jobs:
            self._log_queue_depth(job_ids=job_ids, correlation_id=jobs[0].correlation_id)
            if pipeline_staged and len(jobs) > 1:
                logger.info(
                    "pipeline_staged_enqueue",
                    job_ids=job_ids,
                    correlation_id=jobs[0].correlation_id,
                    enqueued_persona=jobs[0].persona,
                    deferred_personas=[job.persona for job in jobs[1:]],
                )
        return job_ids

    async def _apersist_and_enqueue_jobs(
        self,
        jobs: list[WorkerJob],
        *,
        pipeline_staged: bool = False,
    ) -> list[str]:
        job_ids: list[str] = []
        for index, job in enumerate(jobs):
            self._job_store.upsert_pending(
                job.job_id,
                job.persona,
                correlation_id=job.correlation_id,
                tenant_id=job.tenant_id,
                event_id=job.event_id,
            )
            if not pipeline_staged or index == 0:
                await self._aenqueue_to_queue(job, pipeline_staged=pipeline_staged, index=index)
            job_ids.append(job.job_id)
        if jobs:
            self._log_queue_depth(job_ids=job_ids, correlation_id=jobs[0].correlation_id)
            if pipeline_staged and len(jobs) > 1:
                logger.info(
                    "pipeline_staged_enqueue",
                    job_ids=job_ids,
                    correlation_id=jobs[0].correlation_id,
                    enqueued_persona=jobs[0].persona,
                    deferred_personas=[job.persona for job in jobs[1:]],
                )
        return job_ids

    def enqueue_from_routing_sync(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
        sequential: bool = False,
        pipeline_staged: bool = False,
    ) -> list[str]:
        jobs = jobs_for_routing(
            event_id,
            personas,
            playbook_id=playbook_id,
            payload=payload,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            sequential=sequential,
        )
        return self._persist_and_enqueue_jobs(jobs, pipeline_staged=pipeline_staged)

    async def enqueue_from_routing(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
        sequential: bool = False,
        pipeline_staged: bool = False,
    ) -> list[str]:
        jobs = jobs_for_routing(
            event_id,
            personas,
            playbook_id=playbook_id,
            payload=payload,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            sequential=sequential,
        )
        return await self._apersist_and_enqueue_jobs(jobs, pipeline_staged=pipeline_staged)

    def _should_reject_bus_enqueue(
        self,
        envelope: dict[str, Any],
        *,
        correlation_id: str,
        tenant_id: str,
        msg_type: str,
    ) -> bool:
        payload = envelope.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        finding = payload.get("data", payload)
        if isinstance(finding, dict) and is_noop_finding(finding):
            logger.info(
                "bus_enqueue_rejected_noop_finding",
                correlation_id=correlation_id,
                msg_type=msg_type,
                persona=str(envelope.get("recipient", "")),
            )
            return True

        engagement_id = extract_engagement_id(correlation_id=correlation_id, payload=payload)
        if not engagement_id:
            return False

        guard = self._bus_guard or get_engagement_bus_guard()
        if guard.is_tripped(engagement_id):
            logger.warning("bus_enqueue_rejected_tripped", engagement_id=engagement_id)
            return True

        trip_reason = guard.should_trip(engagement_id)
        if trip_reason is not None and self._engagement_store is not None:
            maybe_trip_engagement(
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                engagement_store=self._engagement_store,
                job_store=self._job_store,
                queue=self._queue,
                bus_guard=guard,
                metrics=self._metrics,
            )
            logger.warning(
                "bus_enqueue_rejected_guard_trip",
                engagement_id=engagement_id,
                reason=trip_reason.value,
            )
            return True

        if self._engagement_store is not None:
            engagement = self._engagement_store.get(tenant_id, engagement_id)
            if engagement is not None and engagement.status in (
                EngagementStatus.CLOSED,
                EngagementStatus.FAILED,
            ):
                logger.warning(
                    "bus_enqueue_rejected_closed",
                    engagement_id=engagement_id,
                    status=engagement.status.value,
                )
                return True

        active_bus_jobs = self._job_store.count_active_bus_jobs(tenant_id, engagement_id)
        if active_bus_jobs >= self._max_jobs_per_engagement:
            logger.warning(
                "bus_enqueue_rejected_rate_limit",
                engagement_id=engagement_id,
                active_bus_jobs=active_bus_jobs,
                limit=self._max_jobs_per_engagement,
            )
            return True
        return False

    async def enqueue_from_bus(self, envelope: dict[str, Any]) -> str:
        """Enqueue a worker job from a bus envelope (delegate/revision/finding handoff)."""
        payload = dict(envelope.get("payload", {}))
        persona = str(envelope.get("recipient", payload.get("persona", "soc")))
        event_id = str(payload.get("event_id", envelope.get("message_id", f"bus-{uuid.uuid4().hex[:8]}")))
        correlation_id = str(payload.get("correlation_id", event_id))
        tenant_id = str(payload.get("tenant_id", "default"))
        msg_type = str(envelope.get("type", "delegate"))
        if self._should_reject_bus_enqueue(
            envelope,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            msg_type=msg_type,
        ):
            return ""

        if msg_type == "revision":
            payload["feedback"] = payload.get("feedback", envelope.get("feedback", ""))
        job = WorkerJob(
            job_id=f"{persona}-bus-{uuid.uuid4().hex[:8]}",
            event_id=event_id,
            persona=persona,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            payload=payload,
            feedback=str(payload.get("feedback", "")),
        )
        self._job_store.upsert_pending(
            job.job_id,
            job.persona,
            correlation_id=job.correlation_id,
            tenant_id=job.tenant_id,
            event_id=job.event_id,
        )
        await self._queue.aenqueue(job)
        engagement_id = extract_engagement_id(correlation_id=correlation_id, payload=payload)
        if engagement_id:
            guard = self._bus_guard or get_engagement_bus_guard()
            guard.record_enqueue(
                engagement_id,
                persona,
                envelope_fingerprint(envelope),
            )
        return job.job_id
