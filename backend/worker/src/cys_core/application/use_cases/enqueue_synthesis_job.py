from __future__ import annotations

import asyncio

from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.application.ports.job_store import JobStorePort
from cys_core.domain.engagement.models import SynthesisStatus
from cys_core.domain.workers.models import WorkerJob


def _latest_finding_entry_for_persona(
    findings_summary: list[dict[str, object]],
    persona: str,
) -> dict[str, object] | None:
    latest: dict[str, object] | None = None
    for item in findings_summary:
        if item.get("persona") == persona:
            latest = item
    return latest


def _dedupe_findings_by_persona(
    findings_summary: list[dict[str, object]],
) -> list[dict[str, object]]:
    latest_by_persona: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for item in findings_summary:
        persona = str(item.get("persona", ""))
        if not persona:
            continue
        if persona not in latest_by_persona:
            order.append(persona)
        latest_by_persona[persona] = item
    return [latest_by_persona[persona] for persona in order]


class EnqueueSynthesisJob:
    """Enqueue final synthesis worker after all specialist personas reach terminal state."""

    def __init__(
        self,
        *,
        engagement_store: EngagementStateStore,
        queue: JobQueueConnector,
        job_store: JobStorePort | None = None,
        engagement_egress: EngagementEgressPort | None = None,
    ) -> None:
        self._engagement_store = engagement_store
        self._queue = queue
        self._job_store = job_store
        self._engagement_egress = engagement_egress

    def _synthesis_job_id(self, synthesis_persona: str, investigation_id: str) -> str:
        return f"{synthesis_persona}-{investigation_id}-synth"

    async def execute(self, job: WorkerJob) -> str | None:
        if job.payload.get("phase") == "synthesis":
            return None

        investigation_id = job.correlation_id or job.event_id
        engagement = await asyncio.to_thread(self._engagement_store.get, job.tenant_id, investigation_id)
        if engagement is None or not engagement.planner_plan:
            return None
        if not engagement.synthesis_persona:
            return None
        if engagement.synthesis_status != SynthesisStatus.PENDING:
            return None

        terminal = set(engagement.completed_personas) | set(engagement.failed_personas)
        if not all(persona in terminal for persona in engagement.planner_plan):
            return None

        if self._job_store is not None:
            active_bus = await asyncio.to_thread(
                self._job_store.count_active_bus_jobs, job.tenant_id, investigation_id
            )
            if active_bus > 0:
                return None

        job_id = self._synthesis_job_id(engagement.synthesis_persona, investigation_id)
        if any(existing.endswith("-synth") for existing in engagement.job_ids):
            return None

        deduped_findings = _dedupe_findings_by_persona(engagement.findings_summary)
        specialist_outcomes: list[dict[str, object]] = []
        for persona in engagement.planner_plan:
            status = "completed" if persona in engagement.completed_personas else "failed"
            entry = _latest_finding_entry_for_persona(engagement.findings_summary, persona)
            finding = entry.get("finding") if entry else None
            specialist_outcomes.append(
                {
                    "persona": persona,
                    "status": status,
                    "finding": finding,
                    "job_id": str(entry.get("job_id", "")) if entry else "",
                }
            )

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
                "findings_summary": deduped_findings,
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
            profile_id=job.profile_id,
        )
        await self._queue.aenqueue(synth_job)
        await asyncio.to_thread(
            self._engagement_store.mark_synthesis_running, job.tenant_id, investigation_id, job_id
        )
        if self._engagement_egress is not None:
            await asyncio.to_thread(
                self._engagement_egress.publish_status,
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
