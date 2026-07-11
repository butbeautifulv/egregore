from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from bootstrap.container import get_container
from cys_core.application.use_cases.engagement_planner import ASYNC_PLANNER_PENDING
from cys_core.application.use_cases.start_engagement import engagement_request_to_security_event
from cys_core.application.use_cases.start_work_order import StartWorkOrder, WorkOrderValidationError
from cys_core.domain.security.auth_models import AuthClaims
from cys_core.domain.work_order.models import WorkOrderRequest
from cys_core.infrastructure.work_order.adapter import WorkOrderStore
from interfaces.api.auth import require_ingress_role, require_operator_role, require_reader_role
from interfaces.api.planner_tasks import spawn_engagement_planner
from interfaces.api.follow_ups import _get_enqueue_follow_up
from interfaces.api.follow_up_schemas import FollowUpIn, FollowUpListOut, FollowUpOut, FollowUpTurnOut
from interfaces.api.work_order_schemas import WorkOrderCreateIn, WorkOrderListOut, WorkOrderOut

router = APIRouter(prefix="/v1", tags=["work-orders"])


def _work_order_store() -> WorkOrderStore:
    return WorkOrderStore(get_container().get_engagement_state_store())


def _start_work_order() -> StartWorkOrder:
    container = get_container()
    return StartWorkOrder(
        work_order_store=_work_order_store(),
        start_engagement=container.get_start_engagement(),
        memory_writer=container.get_memory_write_service(),
        agent_catalog=container.get_agent_catalog(),
        metrics=container.get_metrics_port(),
    )


@router.get("/work-orders", response_model=WorkOrderListOut)
async def list_work_orders(
    tenant_id: str = "default",
    limit: int = 20,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> WorkOrderListOut:
    store = get_container().get_engagement_state_store()
    from cys_core.infrastructure.engagement.postgres_store import PostgresEngagementStateStore

    if isinstance(store, PostgresEngagementStateStore):
        pairs = store.list_recent_with_updated_at(tenant_id, limit=limit)
        return WorkOrderListOut(
            work_orders=[
                WorkOrderOut.from_engagement(eng, updated_at=ts) for eng, ts in pairs
            ],
        )
    engagements = store.list_recent(tenant_id, limit=limit)
    return WorkOrderListOut(
        work_orders=[WorkOrderOut.from_engagement(eng) for eng in engagements],
    )


@router.post("/work-orders", response_model=WorkOrderOut)
async def create_work_order(
    body: WorkOrderCreateIn,
    request: Request,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> WorkOrderOut | JSONResponse:
    wo_request = body.to_domain_request()
    start = _start_work_order()
    try:
        engagement, decision, job_ids = await start.execute(wo_request)
    except WorkOrderValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    out = WorkOrderOut.from_engagement(engagement, decision=decision, job_ids=job_ids)
    if decision.reason == ASYNC_PLANNER_PENDING:
        eng_request = wo_request.to_engagement_request(engagement.id)
        event = engagement_request_to_security_event(eng_request, engagement.id)
        spawn_engagement_planner(
            request,
            start=get_container().get_start_engagement(),
            event=event,
            payload=dict(event.payload),
        )
        return JSONResponse(status_code=202, content=out.model_dump(mode="json"))
    return out


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderOut)
async def get_work_order(
    work_order_id: str,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> WorkOrderOut:
    store = _work_order_store()
    work_order = store.get(tenant_id, work_order_id)
    if work_order is None:
        raise HTTPException(status_code=404, detail="work_order_not_found")
    engagement = get_container().get_engagement_state_store().get(tenant_id, work_order_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="work_order_not_found")
    return WorkOrderOut.from_engagement(engagement)


@router.get("/work-orders/{work_order_id}/follow-ups", response_model=FollowUpListOut)
async def list_work_order_follow_ups(
    work_order_id: str,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> FollowUpListOut:
    use_case = _get_enqueue_follow_up()
    turns = use_case.list_turns(tenant_id, work_order_id)
    return FollowUpListOut(turns=[FollowUpTurnOut(**item) for item in turns])


@router.post("/work-orders/{work_order_id}/follow-ups", response_model=FollowUpOut, status_code=202)
async def create_work_order_follow_up(
    work_order_id: str,
    body: FollowUpIn,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> FollowUpOut:
    tenant_id = body.tenant_id or "default"
    use_case = _get_enqueue_follow_up()
    from cys_core.application.use_cases.enqueue_follow_up import FollowUpError

    try:
        result = use_case.execute(
            tenant_id=tenant_id,
            engagement_id=work_order_id,
            message=body.message,
            mode=body.mode,
            enqueue=body.enqueue,
        )
    except FollowUpError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return FollowUpOut(**result)
