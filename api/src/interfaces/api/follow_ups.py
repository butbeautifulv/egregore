from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from bootstrap.container import get_container
from cys_core.application.use_cases.enqueue_follow_up import FollowUpError
from cys_core.domain.security.auth_models import AuthClaims
from interfaces.api.auth import require_operator_role, require_reader_role
from interfaces.api.authz_helpers import require_engagement_relation
from interfaces.api.follow_up_schemas import FollowUpIn, FollowUpListOut, FollowUpOut, FollowUpTurnOut
from interfaces.api.tenant_deps import require_tenant_match_http

router = APIRouter(prefix="/v1", tags=["follow-ups"])


@router.get("/engagements/{engagement_id}/follow-ups", response_model=FollowUpListOut)
async def list_follow_ups(
    engagement_id: str,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
) -> FollowUpListOut:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    use_case = get_container().get_enqueue_follow_up()
    turns = use_case.list_turns(tenant_id, engagement_id)
    return FollowUpListOut(turns=[FollowUpTurnOut(**item) for item in turns])


@router.post("/engagements/{engagement_id}/follow-ups", response_model=FollowUpOut, status_code=202)
async def create_follow_up(
    engagement_id: str,
    body: FollowUpIn,
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> FollowUpOut:
    tenant_id = require_tenant_match_http(_auth, body.tenant_id or "default")
    require_engagement_relation(
        auth=_auth,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        relation="can_operate",
    )
    use_case = get_container().get_enqueue_follow_up()
    try:
        result = use_case.execute(
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            message=body.message,
            mode=body.mode,
            enqueue=body.enqueue,
        )
    except FollowUpError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return FollowUpOut(**result)
