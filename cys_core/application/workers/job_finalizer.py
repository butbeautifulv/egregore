from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

from cys_core.application.bus_engagement import normalize_correlation_id
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.application.ports.job_store import JobStorePort
from cys_core.application.use_cases.enqueue_next_planned_persona import EnqueueNextPlannedPersona
from cys_core.application.workers.follow_up_publisher import FollowUpAnswerPublisher
from cys_core.domain.catalog.profile_id import resolve_profile_id
from cys_core.domain.security.agent_bus import SecureAgentBus
from cys_core.domain.engagement.models import EngagementStatus
from cys_core.domain.follow_up.models import (
    is_follow_up_orchestrator,
    is_follow_up_payload,
    is_follow_up_plan_iteration,
    is_follow_up_planning,
    work_kind_from_payload,
)
from cys_core.domain.workers.failure_reason import WorkerJobFailureReason, classify_worker_failure
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus

logger = structlog.get_logger(__name__)


class WorkerJobFinalizer:
    def __init__(
        self,
        *,
        job_store: JobStorePort,
        queue: JobQueueConnector,
        bus: SecureAgentBus,
        agent_catalog: AgentCatalogPort,
        engagement_store: EngagementStateStore | None = None,
        engagement_egress: EngagementEgressPort | None = None,
        enqueue_next_planned_persona: EnqueueNextPlannedPersona | None = None,
        enqueue_synthesis_job: EnqueueSynthesisJob | None = None,
        record_sanitizer_block: Callable[[str, str], None] | None = None,
        record_worker_job_failure: Callable[[str, str], None] | None = None,
        follow_up_publisher: FollowUpAnswerPublisher | None = None,
    ) -> None:
        self._job_store = job_store
        self._queue = queue
        self._bus = bus
        self._agent_catalog = agent_catalog
        self._engagement_store = engagement_store
        self._engagement_egress = engagement_egress
        self._enqueue_next_planned_persona = enqueue_next_planned_persona
        self._enqueue_synthesis_job = enqueue_synthesis_job
        self._record_sanitizer_block = record_sanitizer_block or (lambda _where, _mode: None)
        self._record_worker_job_failure = record_worker_job_failure or (lambda _persona, _reason: None)
        self._follow_up_publisher = follow_up_publisher

    def _investigation_id(self, job: WorkerJob) -> str:
        return normalize_correlation_id(job.correlation_id or job.event_id, job.payload)

    async def finalize_failure(
        self,
        job: WorkerJob,
        *,
        exc: BaseException | None = None,
        error_string: str | None = None,
        reason: WorkerJobFailureReason | None = None,
        emit_budget_event: bool = False,
        record_sanitizer: bool = False,
    ) -> WorkerJobFailureReason:
        resolved_reason = reason or classify_worker_failure(exc, error_string=error_string)
        error = (error_string if error_string is not None else (str(exc) if exc else "unknown")).strip()
        investigation_id = self._investigation_id(job)

        logger.warning(
            "worker_job_failed",
            correlation_id=investigation_id,
            engagement_id=investigation_id,
            persona=job.persona,
            job_id=job.job_id,
            reason=resolved_reason.value,
            error_class=type(exc).__name__ if exc else "",
            error=error[:500],
        )
        self._record_worker_job_failure(job.persona, resolved_reason.value)

        if record_sanitizer:
            self._record_sanitizer_block("worker", "hard")

        self._bus.record_agent_failure(job.persona)
        try:
            from cys_core.application.persona_quality_hooks import record_bus_failure, record_job_completed

            catalog_entry = self._agent_catalog.get_agent(job.persona)
            profile_id = resolve_profile_id(payload=job.payload, catalog_entry=catalog_entry)
            record_bus_failure(job.persona, profile_id=profile_id)
            record_job_completed(job.persona, success=False, profile_id=profile_id)
        except Exception:
            pass

        job.transition_to(WorkerJobStatus.FAILED)
        self._job_store.mark_failed(job.job_id)

        if job.payload.get("phase") == "synthesis":
            if self._engagement_store is not None:
                self._engagement_store.fail_synthesis(job.tenant_id, investigation_id, reason=error)
        elif is_follow_up_payload(job.payload):
            if self._follow_up_publisher is not None and job.payload.get("follow_up_id"):
                self._follow_up_publisher.publish_failure(
                    job=job,
                    investigation_id=investigation_id,
                    error=error,
                )
        else:
            self.mark_persona_failed(job)
            await self._enqueue_pipeline_next(job)

        if self._engagement_egress is not None:
            self._engagement_egress.publish_status(
                investigation_id,
                "job_finished",
                {
                    "tenant_id": job.tenant_id,
                    "persona": job.persona,
                    "job_id": job.job_id,
                    "success": False,
                    "error": error,
                    "reason": resolved_reason.value,
                },
            )
            if emit_budget_event:
                from cys_core.domain.workers.job_budget import JobBudgetTracker

                state = JobBudgetTracker.get(f"worker:{job.persona}:{job.job_id}")
                payload = {
                    "tenant_id": job.tenant_id,
                    "persona": job.persona,
                    "job_id": job.job_id,
                    "reason": resolved_reason.value,
                }
                if state is not None:
                    payload.update(
                        {
                            "cost_usd": state.cost_usd,
                            "max_cost_usd": state.max_cost_usd,
                            "tokens_used": state.tokens_used,
                        }
                    )
                self._engagement_egress.publish_event(investigation_id, "budget_exceeded", payload)

        send_dlq = getattr(self._queue, "send_to_dlq", None)
        if send_dlq is not None:
            await send_dlq(job, error)
        self._maybe_close_playbook_engagement(job)
        self._fail_orphan_bus_jobs_if_terminal(job)
        return resolved_reason

    def mark_running(self, job: WorkerJob, session_id: str) -> None:
        job.transition_to(WorkerJobStatus.RUNNING)
        self._job_store.upsert_running(
            job.job_id,
            session_id,
            job.persona,
            correlation_id=job.correlation_id,
            tenant_id=job.tenant_id,
            event_id=job.event_id,
        )

    def publish_job_started(self, job: WorkerJob, investigation_id: str) -> None:
        if self._engagement_egress is None:
            return
        self._engagement_egress.publish_status(
            investigation_id,
            "job_started",
            {"tenant_id": job.tenant_id, "persona": job.persona, "job_id": job.job_id},
        )

    async def mark_success(self, job: WorkerJob, investigation_id: str) -> None:
        job.transition_to(WorkerJobStatus.COMPLETED)
        self._job_store.mark_completed(job.job_id)
        if self._engagement_egress is not None:
            self._engagement_egress.publish_status(
                investigation_id,
                "job_finished",
                {"tenant_id": job.tenant_id, "persona": job.persona, "job_id": job.job_id, "success": True},
            )
        if not is_follow_up_payload(job.payload) or is_follow_up_plan_iteration(job.payload):
            if self._enqueue_next_planned_persona is not None:
                await self._enqueue_next_planned_persona.execute(job)
            if self._enqueue_synthesis_job is not None:
                await self._enqueue_synthesis_job.execute(job)
        if work_kind_from_payload(job.payload) == "follow_up_child":
            pass
        self._maybe_close_playbook_engagement(job)
        self._fail_orphan_bus_jobs_if_terminal(job)
        try:
            from cys_core.application.persona_quality_hooks import record_job_completed

            cost = float(job.payload.get("estimated_cost_usd", 0.0))
            catalog_entry = self._agent_catalog.get_agent(job.persona)
            profile_id = resolve_profile_id(payload=job.payload, catalog_entry=catalog_entry)
            record_job_completed(job.persona, success=True, cost_usd=cost, profile_id=profile_id)
        except Exception:
            pass

    async def mark_follow_up_success(self, job: WorkerJob, investigation_id: str) -> None:
        if self._engagement_store is not None:
            engagement = self._engagement_store.get(job.tenant_id, investigation_id)
            if engagement is not None:
                if not is_follow_up_planning(job.payload):
                    engagement.close_after_follow_up()
                    engagement.follow_up_spawned_job_ids = []
                    self._engagement_store.upsert(engagement)
        await self.mark_success(job, investigation_id)

    async def _enqueue_pipeline_next(self, job: WorkerJob) -> None:
        if self._enqueue_next_planned_persona is not None:
            await self._enqueue_next_planned_persona.execute(job)
        if self._enqueue_synthesis_job is not None:
            await self._enqueue_synthesis_job.execute(job)

    def mark_persona_completed(self, job: WorkerJob) -> None:
        if is_follow_up_payload(job.payload) and not is_follow_up_plan_iteration(job.payload):
            return
        if job.payload.get("phase") == "synthesis":
            return
        if self._engagement_store is None:
            return
        engagement_id = job.correlation_id or job.event_id
        self._engagement_store.mark_persona_done(job.tenant_id, engagement_id, job.persona)
        self._notify_engagement_update(job)

    def mark_persona_failed(self, job: WorkerJob) -> None:
        if is_follow_up_payload(job.payload) and not is_follow_up_plan_iteration(job.payload):
            return
        if job.payload.get("phase") == "synthesis":
            return
        if self._engagement_store is None:
            return
        engagement_id = job.correlation_id or job.event_id
        self._engagement_store.mark_persona_failed(job.tenant_id, engagement_id, job.persona)
        self._notify_engagement_update(job)

    def _notify_engagement_update(self, job: WorkerJob) -> None:
        engagement_id = job.correlation_id or job.event_id
        if self._engagement_egress is None or self._engagement_store is None:
            return
        engagement = self._engagement_store.get(job.tenant_id, engagement_id)
        if engagement is None:
            return
        self._engagement_egress.publish_status(
            engagement_id,
            "job_update",
            {
                "tenant_id": job.tenant_id,
                "status": engagement.status.value,
                "completed_personas": list(engagement.completed_personas),
                "persona": job.persona,
                "planner_status": engagement.planner_status,
            },
        )

    def _fail_orphan_bus_jobs_if_terminal(self, job: WorkerJob) -> None:
        if self._engagement_store is None:
            return
        engagement_id = self._investigation_id(job)
        engagement = self._engagement_store.get(job.tenant_id, engagement_id)
        if engagement is None or not (
            isinstance(engagement.status, EngagementStatus) and engagement.status.is_terminal()
        ):
            return
        for summary in self._job_store.list_by_investigation(job.tenant_id, engagement_id):
            if "-bus-" not in summary.job_id:
                continue
            if summary.status in (WorkerJobStatus.PENDING, WorkerJobStatus.RUNNING):
                self._job_store.mark_failed(summary.job_id)

    def _maybe_close_playbook_engagement(self, job: WorkerJob) -> None:
        if self._engagement_store is None:
            return
        engagement_id = job.correlation_id or job.event_id
        engagement = self._engagement_store.get(job.tenant_id, engagement_id)
        if engagement is None or engagement.planner_plan:
            return
        job_ids = [jid for jid in engagement.job_ids if not jid.endswith("-synth")]
        if not job_ids:
            return
        terminal = {WorkerJobStatus.COMPLETED, WorkerJobStatus.FAILED}
        for job_id in job_ids:
            record = self._job_store.get(job_id)
            if record is not None:
                if record.status not in terminal:
                    return
                continue
            persona = job_id.split("-", 1)[0]
            if persona not in engagement._terminal_personas():
                return
        engagement.status = EngagementStatus.CLOSED
        self._engagement_store.upsert(engagement)
        if self._engagement_egress is not None:
            self._engagement_egress.publish_status(
                engagement_id,
                engagement.status.value,
                {
                    "tenant_id": job.tenant_id,
                    "job_ids": list(engagement.job_ids),
                    "completed_personas": list(engagement.completed_personas),
                    "failed_personas": list(engagement.failed_personas),
                },
            )

    async def mark_budget_failure(self, job: WorkerJob, exc: BaseException | None = None) -> None:
        await self.finalize_failure(
            job,
            exc=exc,
            error_string=str(exc) if exc else "budget_exceeded",
            reason=WorkerJobFailureReason.BUDGET_EXCEEDED,
            emit_budget_event=True,
        )

    async def mark_security_failure(self, job: WorkerJob, exc: BaseException | None = None) -> None:
        await self.finalize_failure(
            job,
            exc=exc,
            error_string=str(exc) if exc else "security_violation",
            record_sanitizer=True,
        )

    async def mark_runtime_failure(self, job: WorkerJob, error: str, exc: BaseException | None = None) -> None:
        await self.finalize_failure(job, exc=exc, error_string=error)
