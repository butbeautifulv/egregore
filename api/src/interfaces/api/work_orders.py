from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from bootstrap.container import get_container
from cys_core.application.use_cases.engagement_planner import ASYNC_PLANNER_PENDING
from cys_core.application.use_cases.start_engagement import engagement_request_to_security_event
from cys_core.application.use_cases.start_work_order import (
    INITIAL_QA_PENDING,
    StartWorkOrder,
    WorkOrderValidationError,
)
from cys_core.domain.security.auth_models import AuthClaims
from interfaces.api.auth import require_ingress_role, require_operator_role, require_reader_role
from interfaces.api.authz_helpers import require_engagement_relation, visible_workspace_ids
from interfaces.api.follow_up_schemas import FollowUpIn, FollowUpListOut, FollowUpOut, FollowUpTurnOut
from interfaces.api.follow_ups import _get_enqueue_follow_up
from interfaces.api.planner_tasks import spawn_engagement_planner
from interfaces.api.tenant_deps import require_tenant_match_http
from interfaces.api.work_order_schemas import WorkOrderCreateIn, WorkOrderListOut, WorkOrderOut

router = APIRouter(prefix="/v1", tags=["work-orders"])

_MAX_LIST_LIMIT = 100


def _work_order_store():
    from cys_core.infrastructure.work_order.adapter import WorkOrderStore

    return WorkOrderStore(get_container().get_engagement_state_store())


def _start_work_order() -> StartWorkOrder:
    container = get_container()
    authz = container.get_authz_service()

    def _write_authz_tuples(tuples):
        authz.write_tuples(tuples)

    return StartWorkOrder(
        work_order_store=_work_order_store(),
        start_engagement=container.get_start_engagement(),
        memory_writer=container.get_memory_write_service(),
        memory_reader=container.get_memory_read_service(),
        agent_catalog=container.get_agent_catalog(),
        metrics=container.get_metrics_port(),
        job_store=container.get_job_store(),
        queue=container.get_job_queue(),
        engagement_egress=container.get_engagement_egress(),
        engagement_store=container.get_engagement_state_store(),
        workspace_store=container.get_workspace_store(),
        authz_tuple_writer=_write_authz_tuples if authz.mode != "off" else None,
    )


@router.get("/work-orders", response_model=WorkOrderListOut)
async def list_work_orders(
    tenant_id: str = "default",
    limit: int = 20,
    cursor: str | None = None,
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> WorkOrderListOut:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    capped_limit = min(max(limit, 1), _MAX_LIST_LIMIT)
    store = get_container().get_engagement_state_store()
    try:
        pairs, next_cursor = store.list_recent_page(
            tenant_id,
            limit=capped_limit,
            cursor=cursor,
        )
    except Exception as exc:
        from cys_core.infrastructure.engagement.list_cursor import InvalidListCursor

        if isinstance(exc, InvalidListCursor):
            raise HTTPException(status_code=400, detail="invalid_cursor") from exc
        raise
    visible = visible_workspace_ids(_auth)
    if visible is not None:
        pairs = [
            (eng, ts)
            for eng, ts in pairs
            if not (getattr(eng, "workspace_id", "") or "") or eng.workspace_id in visible
        ]
    return WorkOrderListOut(
        work_orders=[
            WorkOrderOut.from_engagement(eng, updated_at=ts) for eng, ts in pairs
        ],
        next_cursor=next_cursor,
    )


@router.post("/work-orders", response_model=WorkOrderOut)
async def create_work_order(
    body: WorkOrderCreateIn,
    request: Request,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> WorkOrderOut | JSONResponse:
    tenant_id = require_tenant_match_http(_auth, body.tenant_id)
    wo_request = body.to_domain_request()
    if wo_request.tenant_id != tenant_id:
        wo_request = wo_request.model_copy(update={"tenant_id": tenant_id})
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
    if decision.reason == INITIAL_QA_PENDING:
        return JSONResponse(status_code=202, content=out.model_dump(mode="json"))
    return out


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderOut)
async def get_work_order(
    work_order_id: str,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> WorkOrderOut:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    require_engagement_relation(
        auth=_auth,
        tenant_id=tenant_id,
        engagement_id=work_order_id,
        relation="can_view",
    )
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
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    use_case = _get_enqueue_follow_up()
    turns = use_case.list_turns(tenant_id, work_order_id)
    return FollowUpListOut(turns=[FollowUpTurnOut(**item) for item in turns])


@router.post("/work-orders/{work_order_id}/follow-ups", response_model=FollowUpOut, status_code=202)
async def create_work_order_follow_up(
    work_order_id: str,
    body: FollowUpIn,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> FollowUpOut:
    tenant_id = require_tenant_match_http(_auth, body.tenant_id or "default")
    require_engagement_relation(
        auth=_auth,
        tenant_id=tenant_id,
        engagement_id=work_order_id,
        relation="can_operate",
    )
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
