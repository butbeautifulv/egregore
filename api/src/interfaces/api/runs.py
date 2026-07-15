from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from bootstrap.container import get_container
from cys_core.domain.engagement.models import EngagementMode, EngagementRequest, PlanStrategy
from cys_core.domain.runs.plan_models import PlanApproval
from interfaces.api.tenant_deps import require_tenant_match_http
from cys_core.domain.security.auth_models import AuthClaims
from interfaces.api.auth import require_ingress_role, require_operator_role
from interfaces.api.authz_helpers import require_engagement_relation
from interfaces.api.errors import authz_denied_http
from interfaces.api.run_schemas import RunCreateIn, RunOut, RunStepIn, SessionCreateIn

router = APIRouter(tags=["runs"])


def _deny_legacy_runs_in_enforce() -> None:
    if get_container().get_authz_service().mode == "enforce":
        raise authz_denied_http(
            message="Legacy /runs routes require workspace context; use /v1/work-orders",
        )


def _start_engagement():
    return get_container().get_start_engagement()


async def _create_via_engagement(
    *,
    goal: str,
    profile_id: str,
    tenant_id: str,
    persona: str = "conductor",
) -> dict[str, Any]:
    request = EngagementRequest(
        profile_id=profile_id,
        goal=goal,
        mode=EngagementMode.INTERACTIVE,
        plan_strategy=PlanStrategy.DECLARATIVE,
        input={"persona": persona},
        tenant_id=tenant_id,
    )
    engagement, decision, job_ids = await _start_engagement().execute(request)
    return {
        "run_context": {"context_id": engagement.id, "kind": "job", "tenant_id": engagement.tenant_id},
        "result": {
            "engagement_id": engagement.id,
            "status": engagement.status.value,
            "job_ids": job_ids,
            "playbook_id": decision.playbook_id,
        },
    }


@router.post("/runs", response_model=RunOut)
async def create_run(
    body: RunCreateIn,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> RunOut:
    _deny_legacy_runs_in_enforce()
    tenant_id = require_tenant_match_http(_auth, body.tenant_id)
    out = await _create_via_engagement(
        goal=body.message or body.goal,
        profile_id=body.profile_id,
        tenant_id=tenant_id,
        persona=body.persona,
    )
    return RunOut(run_context=out["run_context"], result=out["result"])


@router.post("/runs/{run_id}/steps", response_model=RunOut)
async def run_step(
    run_id: str,
    body: RunStepIn,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> RunOut:
    _deny_legacy_runs_in_enforce()
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    require_engagement_relation(
        auth=_auth,
        tenant_id=tenant_id,
        engagement_id=run_id,
        relation="can_operate",
    )
    engagement = _start_engagement().get(run_id, tenant_id=tenant_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Run not found")
    # Continuing an in-flight run (vs. the closed-engagement follow-up flow under
    # /v1/engagements/{id}/follow-ups) has no wired implementation — cys_core.application
    # .use_cases.run_step.RunStep exists and is unit-tested but was never connected to a
    # container factory or this route. Report explicitly rather than silently creating an
    # unrelated engagement and mislabeling it as this run (the previous behavior).
    raise HTTPException(status_code=501, detail="Continuing an existing run via /runs/{run_id}/steps is not implemented")


@router.post("/runs/{run_id}/approve-plan", response_model=RunOut)
async def approve_plan(
    run_id: str,
    body: PlanApproval,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> RunOut:
    require_tenant_match_http(_auth, tenant_id)
    # FIXME: routed, auth-gated endpoint that always 501s — engagement-queue approval was never wired up.
    raise HTTPException(status_code=501, detail="Plan approval via engagement queue not implemented")


@router.post("/sessions", response_model=RunOut)
async def create_session(
    body: SessionCreateIn,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> RunOut:
    _deny_legacy_runs_in_enforce()
    tenant_id = require_tenant_match_http(_auth, body.tenant_id)
    out = await _create_via_engagement(
        goal=body.message or body.goal,
        profile_id=body.profile_id,
        tenant_id=tenant_id,
        persona="conductor",
    )
    return RunOut(run_context=out["run_context"], result=out["result"])


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> dict[str, Any]:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    require_engagement_relation(
        auth=_auth,
        tenant_id=tenant_id,
        engagement_id=run_id,
        relation="can_view",
    )
    engagement = _start_engagement().get(run_id, tenant_id=tenant_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_context": {"context_id": engagement.id, "kind": "job", "tenant_id": engagement.tenant_id},
        "state": {"status": engagement.status.value, "goal": engagement.goal},
    }


@router.post("/runs/{run_id}/attachments")
async def upload_attachment(
    run_id: str,
    file: UploadFile = File(...),
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> dict[str, Any]:
    tenant_id = require_tenant_match_http(_auth, tenant_id)
    require_engagement_relation(
        auth=_auth,
        tenant_id=tenant_id,
        engagement_id=run_id,
        relation="can_operate",
    )
    engagement = _start_engagement().get(run_id, tenant_id=tenant_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Run not found")
    max_bytes = get_container().settings.run_attachment_max_bytes
    chunks: list[bytes] = []
    total = 0
    chunk_size = 1024 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail=f"Attachment exceeds max size of {max_bytes} bytes")
        chunks.append(chunk)
    data = b"".join(chunks)
    saved_path = get_container().get_attachment_store().save(tenant_id, run_id, file.filename or "attachment.bin", data)
    return {"path": saved_path, "run_id": run_id}
