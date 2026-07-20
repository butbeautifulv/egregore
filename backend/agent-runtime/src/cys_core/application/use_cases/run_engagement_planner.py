from __future__ import annotations

from typing import Any

from cys_core.application.engagement_streaming import publish_assistant_snapshot
from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.workers.models import WorkerJob


def _engagement_plan_event(job: WorkerJob) -> SecurityEvent:
    """Rebuild the original engagement.start event api enqueued this job for.

    Unlike follow-up re-planning (PlanFollowUpRunner), the initial engagement
    event's full payload (goal/profile_id/plan_strategy/...) already came
    from api's engagement_request_to_security_event() and was carried through
    verbatim in job.payload — no need to reconstruct it from stored
    engagement state.
    """
    return SecurityEvent(
        id=job.event_id,
        type="engagement.start",
        payload=job.payload,
        severity="medium",
        source="engagement-api",
        correlation_id=job.correlation_id or job.event_id,
        tenant_id=job.tenant_id,
    )


class EngagementPlannerRunner:
    """Execute the initial meta-LLM catalog plan for a newly created engagement.

    Triggered by a queued WorkerJob(persona="planner", work_kind="engagement_plan")
    that api enqueues instead of running the planner in-process — api never
    constructs a MetaPlanner (it would need the agent runtime, which must
    never exist in api). This mirrors PlanFollowUpRunner's shape exactly,
    just sourcing the event from the job payload instead of engagement state.
    """

    def __init__(self, *, meta_planner, dispatch, engagement_store, engagement_egress=None) -> None:
        self._meta_planner = meta_planner
        self._dispatch = dispatch
        self._engagement_store = engagement_store
        self._engagement_egress = engagement_egress

    async def execute(self, job: WorkerJob, investigation_id: str) -> dict[str, Any]:
        from cys_core.application.errors import PlanningFailedError

        event = _engagement_plan_event(job)
        profile_id = str(event.payload.get("profile_id") or self._meta_planner.profile_id)

        try:
            plan = await self._meta_planner.execute(event, profile_id=profile_id)
            enriched = {**event.payload, **self._meta_planner.to_worker_jobs_payload(plan)}
            # event.payload is job.payload verbatim (see _engagement_plan_event's
            # docstring) — it carries "work_kind": "engagement_plan" from the
            # planner job itself, and to_worker_jobs_payload() doesn't set its
            # own "work_kind" to override it. Left in place, every specialist
            # job this plan spawns would incorrectly claim to be an
            # engagement-plan job too (harmless today only because every
            # consumer of is_engagement_plan_job() also checks persona=="planner",
            # never bare work_kind — still not data that belongs on a specialist
            # job's payload).
            enriched.pop("work_kind", None)
            job_ids = await self._dispatch.enqueuer.enqueue_from_routing(
                event.id,
                plan.personas,
                playbook_id="engagement-meta-llm",
                payload=enriched,
                correlation_id=investigation_id,
                tenant_id=job.tenant_id,
                sequential=False,
                pipeline_staged=plan.is_pipeline_staged(),
            )
        except Exception as exc:
            if self._engagement_egress is not None:
                self._engagement_egress.publish_status(
                    investigation_id,
                    "error",
                    {"tenant_id": job.tenant_id, "planner_error": str(exc)},
                )
            if isinstance(exc, PlanningFailedError):
                raise
            raise PlanningFailedError(event.id, str(exc)) from exc

        engagement = self._engagement_store.get(job.tenant_id, investigation_id)
        if engagement is not None:
            engagement.mark_enqueued(job_ids)
            self._engagement_store.upsert(engagement)
        if self._engagement_egress is not None:
            self._engagement_egress.publish_status(
                investigation_id,
                "enqueued",
                {
                    "tenant_id": job.tenant_id,
                    "job_ids": job_ids,
                    "personas": plan.personas,
                },
            )
            publish_assistant_snapshot(
                egress=self._engagement_egress,
                engagement_id=investigation_id,
                job_id=job.job_id,
                persona=job.persona,
                tenant_id=job.tenant_id,
                text=(
                    f"Planned {len(plan.personas)} persona(s): "
                    f"{', '.join(plan.personas) if plan.personas else '(none)'}."
                ),
            )
        return {
            "plan": {
                "personas": list(plan.personas),
                "sub_goals": dict(plan.sub_goals or {}),
                "depends_on": dict(plan.depends_on or {}),
                "rationale": plan.rationale or "",
                "execution_mode": plan.execution_mode.value if plan.execution_mode else None,
                "synthesis_persona": plan.synthesis_persona,
            },
            "job_ids": job_ids,
            "summary": f"Planned {len(plan.personas)} persona(s) for engagement.",
        }
