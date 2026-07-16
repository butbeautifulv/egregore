from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from cys_core.application.bus_planner_gate import planner_personas_terminal
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.application.ports.job_store import JobStorePort
from cys_core.application.ports.metrics import MetricsPort
from cys_core.application.use_cases.enqueue_synthesis_job import EnqueueSynthesisJob
from cys_core.application.use_cases.enqueue_worker_jobs import EnqueueWorkerJobs
from cys_core.domain.engagement.models import Engagement, EngagementStatus, ExecutionMode, SynthesisStatus
from cys_core.domain.workers.bus_job_ids import is_bus_worker_job_id
from cys_core.domain.workers.failure_reason import WorkerJobFailureReason
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus

logger = structlog.get_logger(__name__)

_PLANNER_FALLBACK_PERSONAS = ("soc", "intel")


class ReconcileStuckEngagements:
    """Re-enqueue pending synthesis, close degraded engagements, or recover stuck planners."""

    def __init__(
        self,
        *,
        engagement_store: EngagementStateStore,
        job_store: JobStorePort,
        enqueue_synthesis_job: EnqueueSynthesisJob,
        queue: JobQueueConnector | None = None,
        enqueue_worker_jobs: EnqueueWorkerJobs | None = None,
        metrics: MetricsPort | None = None,
        synthesis_stale_multiplier: float,
        default_job_timeout_s: float,
        synth_job_timeout_s: float,
        planner_timeout_seconds: int,
        scan_limit: int,
    ) -> None:
        self._engagement_store = engagement_store
        self._job_store = job_store
        self._enqueue_synthesis_job = enqueue_synthesis_job
        self._queue = queue
        self._enqueue_worker_jobs = enqueue_worker_jobs
        self._metrics = metrics
        self._synthesis_stale_multiplier = synthesis_stale_multiplier
        self._default_job_timeout_s = default_job_timeout_s
        self._synth_job_timeout_s = synth_job_timeout_s
        self._planner_timeout_seconds = planner_timeout_seconds
        self._scan_limit = scan_limit

    async def execute(self, tenant_id: str = "default", *, limit: int | None = None) -> dict[str, int]:
        stats = {
            "scanned": 0,
            "synthesis_enqueued": 0,
            "synthesis_closed_degraded": 0,
            "stale_failed": 0,
            "planner_fallback": 0,
        }
        # list_recent is a blocking Postgres call; this loop runs periodically
        # on the API's shared event loop (see interfaces/api/app.py
        # _reconcile_engagements_loop), so run it off-thread (same pattern
        # used elsewhere in this codebase for sync I/O inside async def).
        resolved_limit = self._scan_limit if limit is None else limit
        engagements = await asyncio.to_thread(
            self._engagement_store.list_recent,
            tenant_id,
            limit=resolved_limit,
        )
        for engagement in engagements:
            stats["scanned"] += 1
            action, stale_failed = await self._reconcile_one(tenant_id, engagement)
            stats[action] = stats.get(action, 0) + 1
            stats["stale_failed"] += stale_failed
        if stats["scanned"]:
            logger.info("engagement_reconcile_complete", tenant_id=tenant_id, **stats)
        return stats

    async def _reconcile_one(self, tenant_id: str, engagement: Engagement) -> tuple[str, int]:
        if engagement.status == EngagementStatus.PLANNING and engagement.planner_status == "planning":
            fallback = await self._maybe_planner_fallback(tenant_id, engagement)
            if fallback:
                return "planner_fallback", 0

        if engagement.status != EngagementStatus.RUNNING:
            return "noop", 0

        if not engagement.planner_plan:
            return "noop", 0

        terminal = planner_personas_terminal(
            list(engagement.planner_plan),
            list(engagement.completed_personas),
            list(engagement.failed_personas),
        )
        if not terminal:
            return "noop", 0

        # _reconcile_stale_bus_jobs, _anchor_job and _is_synth_stale each make
        # several blocking Postgres round-trips (job_store.get/list_*/
        # mark_failed). This method runs per-engagement inside the API's
        # shared-event-loop reconcile background task, so route the sync
        # helpers through a worker thread (same pattern used elsewhere in
        # this codebase for sync I/O inside async def).
        stale_failed = await asyncio.to_thread(self._reconcile_stale_bus_jobs, tenant_id, engagement)
        if stale_failed:
            logger.warning(
                "engagement_reconcile_bus_jobs_failed",
                engagement_id=engagement.id,
                stale_failed=stale_failed,
            )

        if engagement.synthesis_status == SynthesisStatus.PENDING:
            anchor = await asyncio.to_thread(self._anchor_job, tenant_id, engagement)
            if anchor is None:
                return "noop", stale_failed
            job_id = await self._enqueue_synthesis_job.execute(anchor)
            if job_id:
                logger.warning(
                    "engagement_reconcile_synthesis_enqueued",
                    engagement_id=engagement.id,
                    job_id=job_id,
                )
                return "synthesis_enqueued", stale_failed
            return "noop", stale_failed

        if engagement.synthesis_status == SynthesisStatus.RUNNING:
            synth_job_id = next((jid for jid in engagement.job_ids if jid.endswith("-synth")), "")
            is_stale = synth_job_id and await asyncio.to_thread(
                self._is_synth_stale, tenant_id, engagement.id, synth_job_id
            )
            if is_stale:
                await asyncio.to_thread(
                    self._engagement_store.fail_synthesis,
                    tenant_id,
                    engagement.id,
                    reason="synthesis_stale_timeout",
                )
                logger.warning(
                    "engagement_reconcile_synthesis_closed_degraded",
                    engagement_id=engagement.id,
                    job_id=synth_job_id,
                )
                return "synthesis_closed_degraded", stale_failed
        return "noop", stale_failed

    async def _maybe_planner_fallback(self, tenant_id: str, engagement: Engagement) -> bool:
        if engagement.planner_plan or engagement.job_ids:
            return False
        if self._enqueue_worker_jobs is None:
            return False
        if not self._planner_stuck(engagement):
            return False

        personas = list(_PLANNER_FALLBACK_PERSONAS)
        engagement.apply_planner_result(
            personas,
            status="fallback",
            rationale="planner timeout fallback",
            execution_mode=ExecutionMode.STAGED,
            synthesis_persona="consultant",
        )
        payload: dict[str, Any] = {
            "goal": engagement.goal,
            "planner_plan": personas,
            "execution_mode": ExecutionMode.STAGED.value,
            "phase": "specialist",
            "planner_rationale": engagement.planner_rationale,
        }
        job_ids = await self._enqueue_worker_jobs.enqueue_from_routing(
            engagement.id,
            personas,
            playbook_id="engagement-meta-llm",
            payload=payload,
            correlation_id=engagement.id,
            tenant_id=tenant_id,
            pipeline_staged=True,
        )
        engagement.mark_enqueued(job_ids)
        # Blocking Postgres write; offload (same pattern used elsewhere in
        # this codebase for sync I/O inside async def).
        await asyncio.to_thread(self._engagement_store.upsert, engagement)
        if self._metrics is not None:
            self._metrics.record_planner_stuck_fallback()
        logger.warning(
            "engagement_planner_stuck_fallback",
            engagement_id=engagement.id,
            tenant_id=tenant_id,
            job_ids=job_ids,
            personas=personas,
        )
        return bool(job_ids)

    def _planner_stuck(self, engagement: Engagement) -> bool:
        started_raw = engagement.planning_started_at
        if not started_raw:
            return False
        try:
            started = datetime.fromisoformat(started_raw.replace("Z", "+00:00"))
        except ValueError:
            return False
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - started).total_seconds()
        return age >= self._planner_timeout_seconds

    def _anchor_job(self, tenant_id: str, engagement: Engagement) -> WorkerJob | None:
        for job_id in engagement.job_ids:
            if job_id.endswith("-synth") or is_bus_worker_job_id(job_id):
                continue
            record = self._job_store.get(job_id)
            persona = record.persona if record is not None else job_id.split("-", 1)[0]
            return WorkerJob(
                job_id=job_id,
                event_id=engagement.id,
                persona=persona,
                payload={
                    "planner_plan": list(engagement.planner_plan or []),
                    "goal": engagement.goal,
                    "execution_mode": engagement.execution_mode.value if engagement.execution_mode else "",
                },
                correlation_id=engagement.id,
                tenant_id=tenant_id,
            )
        return None

    def _is_synth_stale(self, tenant_id: str, engagement_id: str, job_id: str) -> bool:
        summaries = self._job_store.list_by_investigation(tenant_id, engagement_id)
        summary = next((item for item in summaries if item.job_id == job_id), None)
        if summary is None:
            return False
        if summary.status not in (WorkerJobStatus.PENDING, WorkerJobStatus.RUNNING):
            return False
        if not summary.created_at:
            return False
        from datetime import datetime, timezone

        try:
            started = datetime.fromisoformat(summary.created_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        stale_after = self._synth_job_timeout_s * self._synthesis_stale_multiplier
        now = datetime.now(timezone.utc)
        return (now - started).total_seconds() >= stale_after

    def _reconcile_stale_bus_jobs(self, tenant_id: str, engagement: Engagement) -> int:
        older_than_s = self._default_job_timeout_s * 1.5
        active = self._job_store.list_active_bus_jobs(tenant_id, engagement.id)
        if not active:
            return 0
        stale_ids = {
            item.job_id
            for item in self._job_store.list_stale_bus_jobs(
                tenant_id,
                engagement.id,
                older_than_s=older_than_s,
            )
        }
        terminal_personas = set(engagement.completed_personas) | set(engagement.failed_personas)
        failed = 0
        for summary in active:
            if summary.job_id in stale_ids:
                self._job_store.mark_failed(
                    summary.job_id,
                    error="reconciled_stale_bus_job",
                    reason=WorkerJobFailureReason.CANCELLED.value,
                )
                failed += 1
                continue
            if summary.persona in terminal_personas:
                self._job_store.mark_failed(
                    summary.job_id,
                    error="reconciled_orphan_bus_job",
                    reason=WorkerJobFailureReason.CANCELLED.value,
                )
                failed += 1
        return failed
