from __future__ import annotations

import asyncio

from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.domain.engagement.models import ExecutionMode
from cys_core.domain.workers.models import WorkerJob


class EnqueueNextPlannedPersona:
    """Enqueue the next persona from a multi-step planner plan after upstream success."""

    def __init__(
        self,
        *,
        engagement_store: EngagementStateStore,
        queue: JobQueueConnector,
        engagement_egress: EngagementEgressPort | None = None,
    ) -> None:
        self._engagement_store = engagement_store
        self._queue = queue
        self._engagement_egress = engagement_egress

    async def execute(self, job: WorkerJob) -> str | None:
        investigation_id = job.correlation_id or job.event_id
        engagement = await asyncio.to_thread(self._engagement_store.get, job.tenant_id, investigation_id)
        if engagement is None or not engagement.planner_plan or len(engagement.planner_plan) <= 1:
            return None

        mode = str(job.payload.get("execution_mode", "")).strip().lower()
        if mode == ExecutionMode.PARALLEL:
            return None
        if engagement.execution_mode == ExecutionMode.PARALLEL:
            return None

        next_persona = next(
            (
                persona
                for persona in engagement.planner_plan
                if persona not in engagement.completed_personas and persona not in engagement.failed_personas
            ),
            None,
        )
        if next_persona is None:
            return None

        prefix = f"{next_persona}-"
        job_id = next((candidate for candidate in engagement.job_ids if candidate.startswith(prefix)), None)
        if job_id is None:
            return None

        next_job = WorkerJob(
            job_id=job_id,
            event_id=job.event_id,
            persona=next_persona,
            playbook_id=job.playbook_id,
            payload=job.payload,
            correlation_id=job.correlation_id,
            tenant_id=job.tenant_id,
            profile_id=job.profile_id,
        )
        await self._queue.aenqueue(next_job)
        if self._engagement_egress is not None:
            await asyncio.to_thread(
                self._engagement_egress.publish_status,
                investigation_id,
                "job_enqueued",
                {
                    "tenant_id": job.tenant_id,
                    "persona": next_persona,
                    "job_id": job_id,
                },
            )
        return job_id
