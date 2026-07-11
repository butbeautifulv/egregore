from __future__ import annotations

import json
from typing import Any

from cys_core.application.engagement_streaming import publish_assistant_snapshot
from cys_core.application.use_cases.start_engagement import _pipeline_staged
from cys_core.domain.engagement.models import EngagementStatus, SynthesisStatus
from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.workers.models import WorkerJob


def _follow_up_plan_event(job: WorkerJob, investigation_id: str, engagement) -> SecurityEvent:
    operator_message = str(job.payload.get("operator_message", "")).strip()
    profile_id = ""
    if engagement.intake:
        profile_id = str(engagement.intake.get("profile_id", "") or "")
    goal = operator_message or engagement.follow_up_goal or engagement.goal
    payload: dict[str, Any] = {
        "goal": goal,
        "message": goal,
        "operator_message": operator_message,
        "profile_id": profile_id,
        "plan_strategy": "meta_llm",
        "engagement_mode": "async",
        "follow_up_id": str(job.payload.get("follow_up_id", "")),
        "context_summary": engagement.context_summary,
        "prior_findings_count": len(engagement.findings_summary),
    }
    return SecurityEvent(
        id=investigation_id,
        type="engagement.start",
        payload=payload,
        severity="medium",
        source="follow-up-api",
        correlation_id=investigation_id,
        tenant_id=job.tenant_id,
    )


class PlanFollowUpRunner:
    """Execute catalog planner re-plan for a closed engagement follow-up."""

    def __init__(self, *, meta_planner, dispatch, engagement_store, engagement_egress=None) -> None:
        self._meta_planner = meta_planner
        self._dispatch = dispatch
        self._engagement_store = engagement_store
        self._engagement_egress = engagement_egress

    async def execute(self, job: WorkerJob, investigation_id: str) -> dict[str, Any]:
        engagement = self._engagement_store.get(job.tenant_id, investigation_id)
        if engagement is None:
            raise ValueError("engagement_not_found")

        follow_up_id = str(job.payload.get("follow_up_id", ""))
        operator_message = str(job.payload.get("operator_message", "")).strip()
        engagement.begin_follow_up_planning(
            operator_message=operator_message,
            follow_up_id=follow_up_id,
        )
        self._engagement_store.upsert(engagement)

        if self._engagement_egress is not None and follow_up_id:
            self._engagement_egress.publish_event(
                investigation_id,
                "follow_up_plan_started",
                {
                    "tenant_id": job.tenant_id,
                    "follow_up_id": follow_up_id,
                    "job_id": job.job_id,
                },
            )

        event = _follow_up_plan_event(job, investigation_id, engagement)
        profile_id = str(event.payload.get("profile_id") or self._meta_planner.profile_id)
        plan = await self._meta_planner.execute(event, profile_id=profile_id)
        enriched = {
            **event.payload,
            **self._meta_planner.to_worker_jobs_payload(plan),
            "phase": "follow_up",
            "work_kind": "follow_up_plan",
            "follow_up_id": follow_up_id,
            "operator_message": operator_message,
            "context_id": investigation_id,
        }
        job_ids = await self._dispatch.enqueuer.enqueue_from_routing(
            event.id,
            plan.personas,
            playbook_id="engagement-meta-llm",
            payload=enriched,
            correlation_id=investigation_id,
            tenant_id=job.tenant_id,
            sequential=False,
            pipeline_staged=_pipeline_staged(plan),
        )
        engagement = self._engagement_store.get(job.tenant_id, investigation_id)
        if engagement is not None:
            engagement.mark_enqueued(job_ids)
            engagement.synthesis_status = SynthesisStatus.PENDING
            self._engagement_store.upsert(engagement)

        plan_payload = {
            "personas": list(plan.personas),
            "sub_goals": dict(plan.sub_goals or {}),
            "depends_on": dict(plan.depends_on or {}),
            "rationale": plan.rationale or "",
            "execution_mode": plan.execution_mode.value if plan.execution_mode else None,
            "synthesis_persona": plan.synthesis_persona,
        }
        plan_text = json.dumps(plan_payload, indent=2, ensure_ascii=False)
        if self._engagement_egress is not None:
            publish_assistant_snapshot(
                egress=self._engagement_egress,
                engagement_id=investigation_id,
                job_id=job.job_id,
                persona=job.persona,
                tenant_id=job.tenant_id,
                text=plan_text,
            )
            if self._engagement_egress is not None:
                self._engagement_egress.publish_status(
                    investigation_id,
                    "enqueued",
                    {
                        "tenant_id": job.tenant_id,
                        "job_ids": job_ids,
                        "personas": plan.personas,
                        "follow_up_id": follow_up_id,
                    },
                )

        return {
            "plan": plan_payload,
            "job_ids": job_ids,
            "summary": f"Re-planned {len(plan.personas)} persona(s) for follow-up.",
        }
