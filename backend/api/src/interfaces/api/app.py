from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from bootstrap.container import get_container
from bootstrap.settings import get_settings
from cys_core.domain.security.auth_models import AuthClaims
from cys_core.domain.workers.models import JobResumeRequest
from cys_core.infrastructure.redis_leader import redis_leader
from cys_core.observability.http import mount_metrics
from cys_core.observability.metrics import metrics, seed_agent_trust_gauges
from cys_core.observability.otel import instrument_fastapi, setup_otel
from cys_core.observability.platform_gauges import refresh_platform_gauges
from cys_core.observability.prometheus_setup import register_multiprocess_shutdown
from interfaces.api.auth import require_ingress_role, require_operator_role, require_reader_role
from interfaces.api.authz_helpers import (
    require_engagement_relation,
    require_workspace_relation,
    visible_engagement_ids,
    visible_workspace_ids,
    workspace_id_for_job,
)
from interfaces.api.engagements import _latest_egress_phase
from interfaces.api.schemas import (
    InvestigationDetailOut,
    InvestigationJobsOut,
    InvestigationsListOut,
    InvestigationSummaryOut,
    JobSummaryOut,
)
from interfaces.api.task_supervisor import BackgroundTaskSupervisor
from interfaces.api.tenant_deps import require_tenant_match_http
from interfaces.api.tracing_middleware import tracing_middleware
from interfaces.control_plane.postgres_status_store import PostgresStatusStore
from interfaces.control_plane.status_store import MemoryStatusStore, get_status_store
from interfaces.ingress.router import EventIngress, get_event_ingress
from interfaces.api.hitl_resume import HitlResumeError, resume_worker_job

logger = structlog.get_logger(__name__)


class EventIn(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    severity: str = "medium"
    source: str = ""
    event_id: str | None = None
    correlation_id: str = ""


def create_app(ingress: EventIngress | None = None) -> FastAPI:
    """FastAPI app for event ingest and user status."""

    register_multiprocess_shutdown()
    get_container()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from cys_core.observability.logging_setup import configure_logging

        configure_logging("egregore-api")
        setup_otel(service_name="egregore-api")
        from bootstrap.bus_lifecycle import wire_async_bus
        from cys_core.observability.catalog_drift import verify_critic_intel_recipient

        await wire_async_bus()
        supervisor = BackgroundTaskSupervisor()
        app.state.task_supervisor = supervisor

        async def _refresh_gauges_loop() -> None:
            container = get_container()
            gauge_settings = get_settings()
            while True:
                refresh_platform_gauges(
                    engagement_store=container.get_engagement_state_store(),
                    job_store=container.get_job_store(),
                )
                await asyncio.sleep(gauge_settings.api_gauge_refresh_interval_s)

        async def _reconcile_engagements_loop() -> None:
            container = get_container()
            reconciler = container.get_reconcile_stuck_engagements()
            reconcile_settings = get_settings()
            while True:
                try:
                    async with redis_leader(
                        "egregore:api:reconcile",
                        ttl=reconcile_settings.api_reconcile_leader_ttl_s,
                        redis_url=reconcile_settings.redis_url,
                    ) as is_leader:
                        if is_leader:
                            await reconciler.execute()
                except Exception:
                    logger.exception("engagement_reconcile_loop_failed")
                await asyncio.sleep(reconcile_settings.api_reconcile_interval_s)

        container = get_container()
        verify_critic_intel_recipient(container.get_agent_catalog())
        refresh_platform_gauges(
            engagement_store=container.get_engagement_state_store(),
            job_store=container.get_job_store(),
        )
        supervisor.spawn(_refresh_gauges_loop(), name="refresh-platform-gauges")
        supervisor.spawn(_reconcile_engagements_loop(), name="reconcile-stuck-engagements")
        try:
            yield
        finally:
            await supervisor.shutdown()
            trace_backend = get_container().get_trace_backend()
            trace_backend.flush()
            trace_backend.shutdown()

    app = FastAPI(title="cys-agi event platform", version="0.2.0", lifespan=lifespan)
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ui_cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Workspace-Id"],
    )

    @app.middleware("http")
    async def _tracing_middleware(request: Request, call_next):
        return await tracing_middleware(request, call_next)

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Only reached for exceptions no route/dependency already turned into an
        # HTTPException — FastAPI still dispatches HTTPException to its own default
        # handler first, so this doesn't change any existing intentional error response.
        # Previously such exceptions fell through to Starlette's bare default 500 with no
        # structured log and an inconsistent (non {"code", "message"}) body.
        logger.error(
            "unhandled_api_exception",
            method=request.method,
            path=request.url.path,
            error=str(exc),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "message": "Internal server error"},
        )

    mount_metrics(app)
    instrument_fastapi(app)
    seed_agent_trust_gauges()

    from interfaces.api.catalog import router as catalog_router
    from interfaces.api.engagements import router as engagements_router
    from interfaces.api.follow_ups import router as follow_ups_router
    from interfaces.api.runs import router as runs_router
    from interfaces.api.work_orders import router as work_orders_router
    from interfaces.api.workspaces import router as workspaces_router

    app.include_router(catalog_router)
    app.include_router(runs_router)
    app.include_router(work_orders_router)
    app.include_router(workspaces_router)
    app.include_router(engagements_router)
    app.include_router(follow_ups_router)

    event_ingress = ingress or get_event_ingress()
    store = get_status_store()

    def _job_store():
        return get_container().get_job_store()

    @app.post("/events", response_model=None)
    async def post_event(
        event_in: EventIn,
        request: Request,
        _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)],
    ) -> dict[str, Any] | JSONResponse:
        if get_settings().control_mode != "daemon":
            # interfaces.control_plane is worker-only (see plan §2) — CONTROL_MODE
            # defaults to "inprocess" from before the api/worker split, when a single
            # process could run critic/coordinator inline. In a real split deployment
            # (api has no egregore-worker installed) this is unreachable; set
            # CONTROL_MODE=daemon explicitly wherever api and worker run as separate
            # services (see deploy/docker-compose*.yml) rather than relying on this
            # fallback, which only still works in the transitional shared dev env.
            try:
                from interfaces.control_plane.coordinator_service import get_coordinator_service
                from interfaces.control_plane.critic_service import get_critic_service

                get_critic_service()
                get_coordinator_service()
            except ImportError:
                structlog.get_logger(__name__).warning(
                    "inprocess_control_mode_unavailable",
                    detail="egregore-worker not installed; set CONTROL_MODE=daemon",
                )

        eng_request = None
        from interfaces.api.engagement_ingress import engagement_request_from_event, handle_engagement_ingress

        try:
            eng_request = engagement_request_from_event(
                event_in.event_type,
                event_in.payload,
                correlation_id=event_in.correlation_id,
            )
        except HTTPException:
            raise
        if eng_request is not None:
            tenant_id = require_tenant_match_http(_auth, eng_request.tenant_id)
            if eng_request.tenant_id != tenant_id:
                eng_request = eng_request.model_copy(update={"tenant_id": tenant_id})
            return await handle_engagement_ingress(
                request,
                eng_request=eng_request,
                payload=event_in.payload,
                record_event=store.record_event,
            )

        event, decision, job_ids = await event_ingress.aingest(
            event_in.event_type,
            event_in.payload,
            severity=event_in.severity,
            source=event_in.source,
            event_id=event_in.event_id,
            correlation_id=event_in.correlation_id,
        )
        store.record_event(event.model_dump())

        return {
            "event": event.model_dump(),
            "routing": decision.model_dump(),
            "job_ids": job_ids,
        }

    @app.get("/health")
    async def health() -> dict[str, Any]:
        settings = get_settings()
        return {
            "status": "ok",
            "features": {
                "stream_agent_output": settings.stream_agent_output,
                "stream_agent_tools": settings.stream_agent_output and settings.stream_agent_tools,
            },
        }

    @app.get("/health/infra")
    async def health_infra() -> dict[str, Any]:
        from cys_core.infrastructure.bus_transport import get_bus_transport
        from cys_core.infrastructure.infra_health import collect_infra_health

        container = get_container()
        infra = collect_infra_health(
            queue=container.get_job_queue(),
            egress=container.get_engagement_egress(),
            transport=get_bus_transport(),
            job_store=container.get_job_store(),
        )
        authz = container.get_authz_service()
        infra["openfga"] = {"ok": authz.ping(), "mode": authz.mode}
        return {"status": "ok", **infra}

    @app.get("/status")
    async def get_status(
        _auth: Annotated[AuthClaims | None, Depends(require_reader_role)],
    ) -> dict[str, Any]:
        return store.snapshot()

    @app.get("/status/stream")
    async def status_stream(
        _auth: Annotated[AuthClaims | None, Depends(require_reader_role)],
    ) -> StreamingResponse:
        async def event_generator():
            sse_settings = get_settings()
            if isinstance(store, MemoryStatusStore):
                queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

                def on_event(_kind: str, event: dict[str, Any]) -> None:
                    queue.put_nowait(event)

                unsubscribe = store.subscribe(on_event)
                try:
                    while True:
                        try:
                            event = await asyncio.wait_for(
                                queue.get(),
                                timeout=sse_settings.api_sse_queue_timeout_s,
                            )
                            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                        except TimeoutError:
                            heartbeat = {"kind": "heartbeat", "ts": datetime.now(UTC).isoformat()}
                            yield f"data: {json.dumps(heartbeat)}\n\n"
                finally:
                    unsubscribe()
            elif isinstance(store, PostgresStatusStore):
                last_id = 0
                while True:
                    rows = store.fetch_since(last_id)
                    if rows:
                        for row_id, kind, payload in rows:
                            last_id = row_id
                            event = {
                                "kind": kind,
                                "payload": payload,
                                "ts": datetime.now(UTC).isoformat(),
                            }
                            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    else:
                        heartbeat = {"kind": "heartbeat", "ts": datetime.now(UTC).isoformat()}
                        yield f"data: {json.dumps(heartbeat)}\n\n"
                    await asyncio.sleep(sse_settings.api_sse_retry_sleep_s)
            else:
                heartbeat = {"kind": "heartbeat", "ts": datetime.now(UTC).isoformat()}
                yield f"data: {json.dumps(heartbeat)}\n\n"
                await asyncio.sleep(sse_settings.api_sse_idle_sleep_s)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/investigations", response_model=InvestigationsListOut)
    async def list_investigations(
        response: Response,
        tenant_id: str = "default",
        limit: int = 20,
        cursor: str | None = None,
        _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
    ) -> InvestigationsListOut:
        from cys_core.infrastructure.engagement.list_cursor import InvalidListCursor

        tenant_id = require_tenant_match_http(_auth, tenant_id)
        capped_limit = min(max(limit, 1), 100)
        eng_store = get_container().get_engagement_state_store()
        try:
            pairs, next_cursor = eng_store.list_recent_page(
                tenant_id,
                limit=capped_limit,
                cursor=cursor,
            )
        except InvalidListCursor as exc:
            raise HTTPException(status_code=400, detail="invalid_cursor") from exc
        visible = visible_workspace_ids(_auth)
        engagement_visible = visible_engagement_ids(_auth)
        if visible is not None:
            pairs = [
                (eng, ts)
                for eng, ts in pairs
                if not (getattr(eng, "workspace_id", "") or "") or eng.workspace_id in visible
            ]
        if engagement_visible is not None:
            pairs = [(eng, ts) for eng, ts in pairs if eng.id in engagement_visible]
        if response is not None:
            response.headers["Deprecation"] = "true"
            response.headers["Link"] = '</v1/work-orders>; rel="successor-version"'
        return InvestigationsListOut(
            investigations=[
                InvestigationSummaryOut(
                    investigation_id=eng.id,
                    tenant_id=eng.tenant_id,
                    workspace_id=getattr(eng, "workspace_id", ""),
                    goal=eng.goal,
                    status=eng.status.value,
                    completed_personas=eng.completed_personas,
                )
                for eng, _ts in pairs
            ],
            next_cursor=next_cursor,
        )

    @app.get("/investigations/{investigation_id}", response_model=InvestigationDetailOut)
    async def get_investigation(
        investigation_id: str,
        tenant_id: str = "default",
        _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
    ) -> InvestigationDetailOut:
        tenant_id = require_tenant_match_http(_auth, tenant_id)
        require_engagement_relation(
            auth=_auth,
            tenant_id=tenant_id,
            engagement_id=investigation_id,
            relation="can_view",
        )
        eng_store = get_container().get_engagement_state_store()
        engagement = eng_store.get(tenant_id, investigation_id)
        if engagement is None:
            raise HTTPException(status_code=404, detail="Investigation not found")
        egress = get_container().get_engagement_egress()
        snapshot = getattr(egress, "snapshot", lambda *_a, **_k: [])(investigation_id, tenant_id=tenant_id)
        return InvestigationDetailOut(
            investigation_id=engagement.id,
            tenant_id=engagement.tenant_id,
            workspace_id=getattr(engagement, "workspace_id", ""),
            goal=engagement.goal,
            status=engagement.status.value,
            latest_phase=_latest_egress_phase(snapshot),
            completed_personas=engagement.completed_personas,
            planner_plan=engagement.planner_plan,
            planner_status=engagement.planner_status,
            planner_rationale=engagement.planner_rationale,
            planner_error=engagement.planner_error,
            findings_summary=engagement.findings_summary,
        )

    @app.get("/investigations/{investigation_id}/jobs", response_model=InvestigationJobsOut)
    async def get_investigation_jobs(
        investigation_id: str,
        tenant_id: str = "default",
        _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
    ) -> InvestigationJobsOut:
        tenant_id = require_tenant_match_http(_auth, tenant_id)
        require_engagement_relation(
            auth=_auth,
            tenant_id=tenant_id,
            engagement_id=investigation_id,
            relation="can_view",
        )
        jobs = _job_store().list_by_investigation(tenant_id, investigation_id)
        return InvestigationJobsOut(
            jobs=[
                JobSummaryOut(
                    job_id=job.job_id,
                    persona=job.persona,
                    status=job.status.value,
                    session_id=job.session_id,
                    correlation_id=job.correlation_id,
                    event_id=job.event_id,
                    created_at=job.created_at,
                    follow_up_id=job.follow_up_id,
                    error=job.last_error,
                    reason=job.failure_reason,
                )
                for job in jobs
            ]
        )

    @app.get("/jobs/{job_id}")
    async def get_job(
        job_id: str,
        tenant_id: str = "default",
        _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
    ) -> dict[str, Any]:
        tenant_id = require_tenant_match_http(_auth, tenant_id)
        record = _job_store().get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if record.tenant_id and record.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id": record.job_id,
            "persona": record.persona,
            "status": record.status.value,
            "session_id": record.session_id,
            "pending_hitl": record.pending_hitl.model_dump() if record.pending_hitl else None,
        }

    @app.get("/approvals/pending")
    async def list_pending_approvals(
        _auth: Annotated[AuthClaims | None, Depends(require_operator_role)],
    ) -> dict[str, Any]:
        pending = _job_store().list_pending_approvals()
        visible = visible_workspace_ids(_auth)
        if visible is not None:
            filtered = []
            for item in pending:
                record = _job_store().get(item.job_id)
                if record is None:
                    continue
                ws_id = workspace_id_for_job(record.tenant_id or "default", record)
                if not ws_id or ws_id in visible:
                    filtered.append(item)
            pending = filtered
        metrics.refresh_hitl_pending(len(pending))
        return {"count": len(pending), "approvals": [item.model_dump() for item in pending]}

    @app.post("/jobs/{job_id}/resume")
    async def resume_job(
        job_id: str,
        body: JobResumeRequest,
        tenant_id: str = "default",
        _auth: Annotated[AuthClaims | None, Depends(require_operator_role)] = None,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        tenant_id = require_tenant_match_http(_auth, tenant_id)
        record = _job_store().get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if record.tenant_id and record.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Job not found")
        require_workspace_relation(
            _auth,
            authorization,
            workspace_id_for_job(tenant_id, record),
            "can_operate",
        )
        try:
            return await resume_worker_job(job_id, body)
        except HitlResumeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/workers/process-one")
    async def process_one_worker(
        _auth: Annotated[AuthClaims | None, Depends(require_operator_role)],
    ) -> dict[str, Any]:
        result = await get_container().get_worker_orchestrator().process_next()
        if result is None:
            return {"status": "idle"}
        return {"status": "done", "result": result.model_dump()}

    return app
