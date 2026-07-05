from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.application.ports.job_store import JobStorePort
from cys_core.application.use_cases.enqueue_next_planned_persona import EnqueueNextPlannedPersona
from cys_core.domain.catalog.profile_id import resolve_profile_id
from cys_core.domain.security.agent_bus import SecureAgentBus
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus


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
        record_sanitizer_block: Callable[[str, str], None] | None = None,
    ) -> None:
        self._job_store = job_store
        self._queue = queue
        self._bus = bus
        self._agent_catalog = agent_catalog
        self._engagement_store = engagement_store
        self._engagement_egress = engagement_egress
        self._enqueue_next_planned_persona = enqueue_next_planned_persona
        self._record_sanitizer_block = record_sanitizer_block or (lambda _where, _mode: None)

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
        if self._enqueue_next_planned_persona is not None:
            await self._enqueue_next_planned_persona.execute(job)
        try:
            from cys_core.application.persona_quality_hooks import record_job_completed

            cost = float(job.payload.get("estimated_cost_usd", 0.0))
            catalog_entry = self._agent_catalog.get_agent(job.persona)
            profile_id = resolve_profile_id(payload=job.payload, catalog_entry=catalog_entry)
            record_job_completed(job.persona, success=True, cost_usd=cost, profile_id=profile_id)
        except Exception:
            pass

    async def _enqueue_pipeline_next(self, job: WorkerJob) -> None:
        if self._enqueue_next_planned_persona is None:
            return
        await self._enqueue_next_planned_persona.execute(job)

    def mark_persona_completed(self, job: WorkerJob) -> None:
        if self._engagement_store is None:
            return
        engagement_id = job.correlation_id or job.event_id
        self._engagement_store.mark_persona_done(job.tenant_id, engagement_id, job.persona)
        self._notify_engagement_update(job)

    def mark_persona_failed(self, job: WorkerJob) -> None:
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

    def mark_budget_failure(self, job: WorkerJob) -> None:
        job.transition_to(WorkerJobStatus.FAILED)
        self._job_store.mark_failed(job.job_id)
        self.mark_persona_failed(job)
        if self._engagement_egress is not None:
            engagement_id = job.correlation_id or job.event_id
            from cys_core.domain.workers.job_budget import JobBudgetTracker

            state = JobBudgetTracker.get(f"worker:{job.persona}:{job.job_id}")
            payload = {
                "tenant_id": job.tenant_id,
                "persona": job.persona,
                "job_id": job.job_id,
            }
            if state is not None:
                payload.update(
                    {
                        "cost_usd": state.cost_usd,
                        "max_cost_usd": state.max_cost_usd,
                        "tokens_used": state.tokens_used,
                    }
                )
            self._engagement_egress.publish_event(engagement_id, "budget_exceeded", payload)

    def mark_security_failure(self, job: WorkerJob) -> None:
        self._record_sanitizer_block("worker", "hard")
        job.transition_to(WorkerJobStatus.FAILED)
        self._job_store.mark_failed(job.job_id)
        self.mark_persona_failed(job)

    async def mark_runtime_failure(self, job: WorkerJob, error: str) -> None:
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
        self.mark_persona_failed(job)
        await self._enqueue_pipeline_next(job)
        if self._engagement_egress is not None:
            investigation_id = job.correlation_id or job.event_id
            self._engagement_egress.publish_status(
                investigation_id,
                "job_finished",
                {
                    "tenant_id": job.tenant_id,
                    "persona": job.persona,
                    "job_id": job.job_id,
                    "success": False,
                    "error": error,
                },
            )
        send_dlq = getattr(self._queue, "send_to_dlq", None)
        if send_dlq is not None:
            await send_dlq(job, error)
