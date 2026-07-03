from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from cys_core.infrastructure.catalog.hybrid_registry import get_agent_catalog
from cys_core.application.use_cases.manage_run import ManageRun
from cys_core.domain.runs.plan_models import PlanApproval
from cys_core.domain.security.auth_models import AuthClaims
from cys_core.infrastructure.runs.factory import get_attachment_store, get_run_state_store, get_work_todo_store
from cys_core.runtime.agent import get_runtime
from bootstrap.container import get_container
from interfaces.api.auth import require_ingress_role, require_operator_role
from interfaces.api.run_errors import raise_run_api_error
from interfaces.api.run_schemas import RunCreateIn, RunOut, RunStepIn, SessionCreateIn, new_job_context, new_session_context

router = APIRouter(tags=["runs"])


def _manage_run() -> ManageRun:
    container = get_container()
    return ManageRun(
        runtime=get_runtime(),
        state_store=get_run_state_store(),
        catalog=get_agent_catalog(),
        todo_store=get_work_todo_store(),
        judge_backend=container.get_judge_backend(),
    )


@router.post("/runs", response_model=RunOut)
async def create_run(
    body: RunCreateIn,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> RunOut:
    ctx = new_job_context(body)
    user_input = body.message or body.goal
    manage = _manage_run()
    manage.save_context(ctx, goal=user_input)
    if body.file_paths:
        _attach_paths_to_run(ctx.tenant_id, ctx.context_id, ctx.kind.value, body.file_paths)
    try:
        out = await manage.create_and_step(ctx, user_input, persona=body.persona)
    except Exception as exc:
        raise_run_api_error(exc)
    return RunOut(run_context=out["run_context"], result=out["result"])


@router.post("/runs/{run_id}/steps", response_model=RunOut)
async def run_step(
    run_id: str,
    body: RunStepIn,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> RunOut:
    try:
        out = await _manage_run().step(run_id, body.message, tenant_id=tenant_id, mode=body.mode)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None
    except Exception as exc:
        raise_run_api_error(exc)
    return RunOut(run_context=out["run_context"], result=out["result"])


@router.post("/runs/{run_id}/approve-plan", response_model=RunOut)
async def approve_plan(
    run_id: str,
    body: PlanApproval,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
) -> RunOut:
    try:
        out = await _manage_run().approve_plan(run_id, body, tenant_id=tenant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None
    except Exception as exc:
        raise_run_api_error(exc)
    return RunOut(run_context=out["run_context"], result=out["result"])


@router.post("/sessions", response_model=RunOut)
async def create_session(
    body: SessionCreateIn,
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> RunOut:
    ctx = new_session_context(body)
    user_input = body.message or body.goal
    try:
        out = await _manage_run().create_and_step(ctx, user_input, persona="conductor")
    except Exception as exc:
        raise_run_api_error(exc)
    return RunOut(run_context=out["run_context"], result=out["result"])


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> dict[str, Any]:
    store = get_run_state_store()
    try:
        ctx = _manage_run().get_context(run_id, tenant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None
    state = store.get(tenant_id, run_id, ctx.kind.value)
    return {
        "run_context": ctx.model_dump(),
        "state": state.model_dump() if state else None,
    }


def _attach_paths_to_run(tenant_id: str, run_id: str, kind: str, paths: list[str]) -> None:
    store = get_run_state_store()
    state = store.get(tenant_id, run_id, kind)
    if state is None:
        return
    attachments = [{"path": path, "name": path.rsplit("/", 1)[-1]} for path in paths]
    state.attachments = [*state.attachments, *attachments]
    store.upsert(state)


@router.post("/runs/{run_id}/attachments")
async def upload_attachment(
    run_id: str,
    file: UploadFile = File(...),
    tenant_id: str = "default",
    _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)] = None,
) -> dict[str, Any]:
    store = get_run_state_store()
    try:
        ctx = _manage_run().get_context(run_id, tenant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None
    data = await file.read()
    saved_path = get_attachment_store().save(tenant_id, run_id, file.filename or "attachment.bin", data)
    state = store.get(tenant_id, run_id, ctx.kind.value)
    if state is not None:
        state.attachments = [*state.attachments, {"path": saved_path, "name": file.filename or "attachment.bin"}]
        store.upsert(state)
    return {"path": saved_path, "run_id": run_id}
