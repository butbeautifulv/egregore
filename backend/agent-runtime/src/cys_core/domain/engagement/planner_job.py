from __future__ import annotations

from typing import Any

#: Reserved persona/work_kind pair used to route the initial meta-LLM
#: engagement plan through the normal per-persona job queue instead of
#: inventing a second queueing mechanism. api enqueues this job (pure data,
#: no runtime); worker's RunWorkerJob recognizes it and hands it to
#: EngagementPlannerRunner instead of the regular per-persona agent pipeline.
ENGAGEMENT_PLAN_WORK_KIND = "engagement_plan"
ENGAGEMENT_PLANNER_PERSONA = "planner"


def is_engagement_plan_job(payload: dict[str, Any], *, persona: str) -> bool:
    return (
        persona == ENGAGEMENT_PLANNER_PERSONA
        and str(payload.get("work_kind", "")) == ENGAGEMENT_PLAN_WORK_KIND
    )
