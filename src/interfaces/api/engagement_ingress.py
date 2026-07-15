from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from bootstrap.container import get_container
from cys_core.application.use_cases.engagement_planner import ASYNC_PLANNER_PENDING
from cys_core.domain.engagement.models import EngagementMode, EngagementRequest, PlanStrategy
from cys_core.application.use_cases.start_engagement import engagement_request_to_security_event
from interfaces.api.planner_tasks import spawn_engagement_planner


async def handle_engagement_ingress(
    request: Request,
    *,
    eng_request: EngagementRequest,
    payload: dict[str, Any],
    record_event,
) -> dict[str, Any] | JSONResponse:
    start = get_container().get_start_engagement()
    engagement, decision, job_ids = await start.execute(eng_request)
    event = engagement_request_to_security_event(eng_request, engagement.id)
    record_event(event.model_dump())
    if decision.reason == ASYNC_PLANNER_PENDING:
        spawn_engagement_planner(request, start=start, event=event, payload=payload)
        return JSONResponse(
            status_code=202,
            content={
                "event": event.model_dump(),
                "routing": decision.model_dump(),
                "job_ids": job_ids,
                "accepted": True,
                "planner_status": "planning",
                "investigation_id": engagement.id,
            },
        )
    return {
        "event": event.model_dump(),
        "routing": decision.model_dump(),
        "job_ids": job_ids,
        "investigation_id": engagement.id,
    }


def engagement_request_from_event(event_type: str, payload: dict[str, Any], *, correlation_id: str = "") -> EngagementRequest | None:
    if event_type != "engagement.start":
        return None
    goal = str(payload.get("goal", payload.get("message", payload.get("query", ""))))
    if not goal:
        raise HTTPException(status_code=400, detail="engagement.start requires goal; use POST /v1/engagements")
    raw_plan = str(payload.get("plan_strategy", PlanStrategy.META_LLM.value))
    try:
        plan_strategy = PlanStrategy(raw_plan)
    except ValueError:
        plan_strategy = PlanStrategy.META_LLM
    return EngagementRequest(
        profile_id=str(payload.get("profile_id", "cybersec-soc")),
        domain_id=str(payload.get("domain_id", "cybersecurity")),
        goal=goal,
        mode=EngagementMode(str(payload.get("engagement_mode", EngagementMode.ASYNC.value))),
        plan_strategy=plan_strategy,
        input=dict(payload),
        tenant_id=str(payload.get("tenant_id", "default")),
        correlation_id=correlation_id,
    )
