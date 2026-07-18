from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from bootstrap.container import get_container
from cys_core.application.use_cases.engagement_planner import ASYNC_PLANNER_PENDING
from cys_core.application.use_cases.start_work_order import (
    INITIAL_QA_PENDING,
    WorkOrderValidationError,
)
from cys_core.domain.parsing.json_text import parse_json_text
from cys_core.domain.security.auth_models import AuthClaims
from cys_core.domain.work_order.models import WorkOrderRequest
from interfaces.api.auth import require_ingress_role, require_reader_role
from interfaces.api.authz_helpers import (
    filter_by_visible_workspaces,
    require_engagement_relation,
    visible_workspace_ids,
)
from interfaces.api.engagement_schemas import (
    EngagementCreateIn,
    EngagementListOut,
    EngagementMemoryOut,
    EngagementOut,
    MemoryEntryOut,
    PromotePlanIn,
    TenantMemoryOut,
)
from interfaces.api.tenant_deps import require_tenant_match_http

router = APIRouter(prefix="/v1", tags=["engagements"])  # legacy alias — delegates to StartWorkOrder


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
    updated_at=None,
) -> EngagementOut:
    return EngagementOut(
        engagement_id=engagement.id,
        status=status or engagement.status.value,
        workspace_id=getattr(engagement, "workspace_id", ""),
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
        planner_sub_goals=engagement.planner_sub_goals,
        planner_depends_on=engagement.planner_depends_on,
        findings_summary=engagement.findings_summary,
        execution_mode=engagement.execution_mode.value if engagement.execution_mode else None,
        synthesis_persona=engagement.synthesis_persona,
        synthesis_status=engagement.synthesis_status.value if engagement.synthesis_status else None,
        final_report=engagement.final_report,
        updated_at=updated_at,
    )


@router.get("/engagements", response_model=EngagementListOut)
async def list_engagements(
    tenant_id: str = "default",
    limit: int = 20,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> EngagementListOut:
    return await asyncio.to_thread(_list_engagements_impl, tenant_id, limit, _auth)


def _list_engagements_impl(tenant_id: str, limit: int, _auth: AuthClaims | None) -> EngagementListOut:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    store = get_container().get_engagement_state_store()
    list_with_updated_at = getattr(store, "list_recent_with_updated_at", None)
    visible = visible_workspace_ids(_auth)

    def _visible(engagement) -> bool:
        if visible is None:
            return True
        workspace_id = (getattr(engagement, "workspace_id", "") or "").strip()
        return not workspace_id or workspace_id in visible

    if list_with_updated_at is not None:
        pairs = list_with_updated_at(tenant_id, limit=limit)
        return EngagementListOut(
            engagements=[
                _engagement_out(eng, updated_at=ts)
                for eng, ts in pairs
                if _visible(eng)
            ],
        )
    engagements = filter_by_visible_workspaces(store.list_recent(tenant_id, limit=limit), visible)
    return EngagementListOut(engagements=[_engagement_out(eng) for eng in engagements])


@router.post("/engagements", response_model=EngagementOut)
async def create_engagement(
    body: EngagementCreateIn,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> EngagementOut | JSONResponse:
    # Legacy entry point — delegates to StartWorkOrder (the same use case
    # POST /v1/work-orders calls) so there is exactly one real
    # implementation underneath both routes. See
    # docs/MICROSERVICES_SPLIT_PLAN.md §16.9/task #61: kept for callers that
    # depend on this URL directly rather than removed, since both existing
    # UI clients already prefer /v1/work-orders and only fall back here on
    # 404.
    tenant_id = require_tenant_match_http(_auth, body.tenant_id)
    wo_request = WorkOrderRequest(
        profile_id=body.profile_id,
        domain_id=body.domain_id,
        workspace_id=body.workspace_id,
        goal=body.goal,
        intake=body.input,
        mode=body.mode,
        plan_strategy=body.plan_strategy,
        tenant_id=tenant_id,
        correlation_id=body.correlation_id,
    )
    start = get_container().get_start_work_order()
    try:
        engagement, decision, job_ids = await start.execute(wo_request)
    except WorkOrderValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    out = _engagement_out(engagement, decision=decision, job_ids=job_ids)
    if decision.reason in (ASYNC_PLANNER_PENDING, INITIAL_QA_PENDING):
        # StartWorkOrder already enqueued the planner/initial-QA WorkerJob —
        # worker picks up from here, nothing left to trigger.
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
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> EngagementOut:
    return await asyncio.to_thread(_get_engagement_impl, engagement_id, tenant_id, _auth)


def _get_engagement_impl(engagement_id: str, tenant_id: str, _auth: AuthClaims | None) -> EngagementOut:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    require_engagement_relation(
        auth=_auth,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        relation="can_view",
    )
    store = get_container().get_engagement_state_store()
    engagement = store.get(tenant_id, engagement_id)
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
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> EngagementMemoryOut:
    return await asyncio.to_thread(
        _get_engagement_memory_impl, engagement_id, tenant_id, agent, memory_type, limit, _auth
    )


def _get_engagement_memory_impl(
    engagement_id: str,
    tenant_id: str,
    agent: str | None,
    memory_type: str | None,
    limit: int,
    _auth: AuthClaims | None,
) -> EngagementMemoryOut:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    require_engagement_relation(
        auth=_auth,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        relation="can_view",
    )
    store = get_container().get_engagement_state_store()
    engagement = store.get(tenant_id, engagement_id)
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
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> TenantMemoryOut:
    return await asyncio.to_thread(_list_tenant_memory_impl, tenant_id, agent, limit, _auth)


def _list_tenant_memory_impl(
    tenant_id: str, agent: str | None, limit: int, _auth: AuthClaims | None
) -> TenantMemoryOut:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    cap = min(max(limit, 1), 200)
    reader = get_container().get_memory_read_service()
    entries = reader.list_by_tenant(tenant_id, limit=cap, agent=agent)
    visible = visible_workspace_ids(_auth)
    if visible is not None:
        eng_store = get_container().get_engagement_state_store()
        filtered = []
        for entry in entries:
            investigation_id = entry.scope.investigation_id
            engagement = eng_store.get(tenant_id, investigation_id)
            if engagement is None:
                continue
            workspace_id = (getattr(engagement, "workspace_id", "") or "").strip()
            if not workspace_id or workspace_id in visible:
                filtered.append(entry)
        entries = filtered
    return TenantMemoryOut(entries=[_memory_entry_out(entry) for entry in entries])


@router.post("/engagements/{engagement_id}/promote-plan")
async def promote_engagement_plan(
    engagement_id: str,
    body: PromotePlanIn,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> dict:
    return await asyncio.to_thread(_promote_engagement_plan_impl, engagement_id, body, tenant_id, _auth)


def _promote_engagement_plan_impl(
    engagement_id: str, body: PromotePlanIn, tenant_id: str, _auth: AuthClaims | None
) -> dict:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
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
    return await asyncio.to_thread(_list_engagement_events_impl, engagement_id, tenant_id, _auth)


def _list_engagement_events_impl(engagement_id: str, tenant_id: str, _auth: AuthClaims | None) -> list[dict]:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    require_engagement_relation(
        auth=_auth,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        relation="can_view",
    )
    engagement = get_container().get_engagement_state_store().get(tenant_id, engagement_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Engagement not found")
    egress = get_container().get_engagement_egress()
    snapshot = getattr(egress, "snapshot", lambda *_a, **_k: [])(engagement_id, tenant_id=tenant_id)
    return snapshot


@router.get("/engagements/{engagement_id}/stream")
async def stream_engagement(
    engagement_id: str,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> StreamingResponse:
    tenant_id = await asyncio.to_thread(_stream_engagement_precheck, engagement_id, tenant_id, _auth)
    egress = get_container().get_engagement_egress()

    async def _gen():
        import json

        async for event in egress.subscribe(engagement_id, tenant_id=tenant_id):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


def _stream_engagement_precheck(engagement_id: str, tenant_id: str, _auth: AuthClaims | None) -> str:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    require_engagement_relation(
        auth=_auth,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        relation="can_view",
    )
    return tenant_id
