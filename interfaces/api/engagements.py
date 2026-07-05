from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from bootstrap.container import get_container
from cys_core.application.use_cases.engagement_planner import ASYNC_PLANNER_PENDING
from cys_core.application.use_cases.start_engagement import engagement_request_to_security_event
from cys_core.domain.parsing.json_text import parse_json_text
from cys_core.domain.security.auth_models import AuthClaims
from interfaces.api.auth import require_ingress_role, require_reader_role
from interfaces.api.engagement_schemas import (
    EngagementCreateIn,
    EngagementListOut,
    EngagementMemoryOut,
    EngagementOut,
    MemoryEntryOut,
    PromotePlanIn,
    TenantMemoryOut,
)
from interfaces.api.planner_tasks import spawn_engagement_planner

router = APIRouter(prefix="/v1", tags=["engagements"])


def _latest_egress_phase(snapshot: list) -> str | None:
    if not snapshot:
        return None
    latest = snapshot[-1]
    phase = str(latest.get("phase", latest.get("type", ""))).strip()
    return phase or None


def _engagement_out(
    engagement,
    *,
    status: str | None = None,
    latest_phase: str | None = None,
    decision=None,
    job_ids=None,
) -> EngagementOut:
    return EngagementOut(
        engagement_id=engagement.id,
        status=status or engagement.status.value,
        latest_phase=latest_phase,
        job_ids=job_ids if job_ids is not None else engagement.job_ids,
        playbook_id=decision.playbook_id if decision is not None else "",
        reason=decision.reason if decision is not None else "",
        goal=engagement.goal,
        completed_personas=engagement.completed_personas,
        failed_personas=engagement.failed_personas,
        planner_plan=engagement.planner_plan,
        planner_status=engagement.planner_status,
        planner_rationale=engagement.planner_rationale,
        planner_error=engagement.planner_error,
        findings_summary=engagement.findings_summary,
    )


@router.get("/engagements", response_model=EngagementListOut)
async def list_engagements(
    tenant_id: str = "default",
    limit: int = 20,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> EngagementListOut:
    store = get_container().get_engagement_state_store()
    engagements = store.list_recent(tenant_id, limit=limit)
    return EngagementListOut(engagements=[_engagement_out(eng) for eng in engagements])


@router.post("/engagements", response_model=EngagementOut)
async def create_engagement(
    body: EngagementCreateIn,
    request: Request,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> EngagementOut | JSONResponse:
    eng_request = body.to_domain_request()
    start = get_container().get_start_engagement()
    engagement, decision, job_ids = await start.execute(eng_request)
    out = _engagement_out(engagement, decision=decision, job_ids=job_ids)
    if decision.reason == ASYNC_PLANNER_PENDING:
        event = engagement_request_to_security_event(eng_request, engagement.id)
        spawn_engagement_planner(request, start=start, event=event, payload=dict(event.payload))
        return JSONResponse(
            status_code=202,
            content={
                **out.model_dump(),
                "accepted": True,
                "planner_status": "planning",
            },
        )
    return out


@router.get("/engagements/{engagement_id}", response_model=EngagementOut)
async def get_engagement(
    engagement_id: str,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> EngagementOut:
    start = get_container().get_start_engagement()
    engagement = start.get(engagement_id, tenant_id=tenant_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Engagement not found")
    egress = get_container().get_engagement_egress()
    snapshot = getattr(egress, "snapshot", lambda *_a, **_k: [])(engagement_id, tenant_id=tenant_id)
    return _engagement_out(
        engagement,
        status=engagement.status.value,
        latest_phase=_latest_egress_phase(snapshot),
    )


@router.get("/engagements/{engagement_id}/memory", response_model=EngagementMemoryOut)
async def get_engagement_memory(
    engagement_id: str,
    tenant_id: str = "default",
    agent: str | None = None,
    memory_type: str | None = None,
    limit: int = 50,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> EngagementMemoryOut:
    start = get_container().get_start_engagement()
    engagement = start.get(engagement_id, tenant_id=tenant_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Engagement not found")

    cap = min(max(limit, 1), 100)
    reader = get_container().get_memory_read_service()
    entries = reader.query_investigation(tenant_id, engagement_id, limit=cap)
    if agent:
        entries = [entry for entry in entries if entry.source_agent == agent]
    if memory_type:
        entries = [entry for entry in entries if entry.memory_type == memory_type]
    entries.sort(key=lambda item: item.created_at, reverse=True)
    entries = entries[:cap]

    return EngagementMemoryOut(
        entries=[
            MemoryEntryOut(
                id=entry.id,
                investigation_id=entry.scope.investigation_id,
                source_agent=entry.source_agent,
                source_job_id=entry.source_job_id,
                memory_type=entry.memory_type,
                trust_score=entry.trust_score,
                content=entry.content,
                content_parsed=parse_json_text(entry.content),
                created_at=entry.created_at,
            )
            for entry in entries
        ]
    )


def _memory_entry_out(entry) -> MemoryEntryOut:
    return MemoryEntryOut(
        id=entry.id,
        investigation_id=entry.scope.investigation_id,
        source_agent=entry.source_agent,
        source_job_id=entry.source_job_id,
        memory_type=entry.memory_type,
        trust_score=entry.trust_score,
        content=entry.content,
        content_parsed=parse_json_text(entry.content),
        created_at=entry.created_at,
    )


@router.get("/memory", response_model=TenantMemoryOut)
async def list_tenant_memory(
    tenant_id: str = "default",
    agent: str | None = None,
    limit: int = 100,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> TenantMemoryOut:
    cap = min(max(limit, 1), 200)
    reader = get_container().get_memory_read_service()
    entries = reader.list_by_tenant(tenant_id, limit=cap, agent=agent)
    return TenantMemoryOut(entries=[_memory_entry_out(entry) for entry in entries])


@router.post("/engagements/{engagement_id}/promote-plan")
async def promote_engagement_plan(
    engagement_id: str,
    body: PromotePlanIn,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> dict:
    from cys_core.application.use_cases.promote_engagement_plan import (
        PromoteEngagementPlanError,
        PromoteEngagementPlanToCatalog,
    )
    from interfaces.api.deps import api_actor

    container = get_container()
    use_case = PromoteEngagementPlanToCatalog(
        container.get_engagement_state_store(),
        container.get_catalog_mutation_service(),
        activate_plan=lambda plan_id, profile_id: container.get_plan_catalog().activate_plan(
            plan_id, profile_id=profile_id
        ),
    )
    try:
        saved = use_case.execute(
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            plan_id=body.plan_id,
            activate=body.activate,
            actor=api_actor(_auth),
        )
    except PromoteEngagementPlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return saved.model_dump(mode="json")


@router.get("/engagements/{engagement_id}/events")
async def list_engagement_events(
    engagement_id: str,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> list[dict]:
    start = get_container().get_start_engagement()
    engagement = start.get(engagement_id, tenant_id=tenant_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Engagement not found")
    egress = get_container().get_engagement_egress()
    snapshot = getattr(egress, "snapshot", lambda *_a, **_k: [])(engagement_id, tenant_id=tenant_id)
    return snapshot


@router.get("/engagements/{engagement_id}/stream")
async def stream_engagement(
    engagement_id: str,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> StreamingResponse:
    egress = get_container().get_engagement_egress()

    async def _gen():
        import json

        async for event in egress.subscribe(engagement_id, tenant_id=tenant_id):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")
