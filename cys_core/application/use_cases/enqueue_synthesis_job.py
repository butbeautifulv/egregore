from __future__ import annotations

from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.domain.engagement.models import SynthesisStatus
from cys_core.domain.workers.models import WorkerJob


class EnqueueSynthesisJob:
    """Enqueue final synthesis worker after all specialist personas reach terminal state."""

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

    def _synthesis_job_id(self, synthesis_persona: str, investigation_id: str) -> str:
        return f"{synthesis_persona}-{investigation_id}-synth"

    async def execute(self, job: WorkerJob) -> str | None:
        if job.payload.get("phase") == "synthesis":
            return None

        investigation_id = job.correlation_id or job.event_id
        engagement = self._engagement_store.get(job.tenant_id, investigation_id)
        if engagement is None or not engagement.planner_plan:
            return None
        if not engagement.synthesis_persona:
            return None
        if engagement.synthesis_status != SynthesisStatus.PENDING:
            return None

        terminal = set(engagement.completed_personas) | set(engagement.failed_personas)
        if not all(persona in terminal for persona in engagement.planner_plan):
            return None

        job_id = self._synthesis_job_id(engagement.synthesis_persona, investigation_id)
        if any(existing.endswith("-synth") for existing in engagement.job_ids):
            return None

        specialist_outcomes: list[dict[str, object]] = []
        for persona in engagement.planner_plan:
            status = "completed" if persona in engagement.completed_personas else "failed"
            finding = next(
                (item.get("finding") for item in engagement.findings_summary if item.get("persona") == persona),
                None,
            )
            specialist_outcomes.append({"persona": persona, "status": status, "finding": finding})

        synth_job = WorkerJob(
            job_id=job_id,
            event_id=job.event_id,
            persona=engagement.synthesis_persona,
            playbook_id=job.playbook_id,
            payload={
                **job.payload,
                "phase": "synthesis",
                "goal": engagement.goal,
                "planner_plan": list(engagement.planner_plan),
                "planner_rationale": engagement.planner_rationale,
                "findings_summary": list(engagement.findings_summary),
                "evidence_manifests": {
                    persona: manifest
                    for persona in engagement.planner_plan
                    if (manifest := engagement.evidence_manifests.get(persona)) is not None
                },
                "specialist_outcomes": specialist_outcomes,
                "failed_personas": list(engagement.failed_personas),
            },
            correlation_id=job.correlation_id,
            tenant_id=job.tenant_id,
        )
        await self._queue.aenqueue(synth_job)
        self._engagement_store.mark_synthesis_running(job.tenant_id, investigation_id, job_id)
        if self._engagement_egress is not None:
            self._engagement_egress.publish_status(
                investigation_id,
                "job_enqueued",
                {
                    "tenant_id": job.tenant_id,
                    "persona": engagement.synthesis_persona,
                    "job_id": job_id,
                    "phase": "synthesis",
                },
            )
        return job_id
