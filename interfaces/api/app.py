from __future__ import annotations

import cys_core.observability.prometheus_setup  # noqa: F401 — multiprocess atexit
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from bootstrap.container import get_container
from bootstrap.settings import get_settings
from cys_core.domain.security.auth_models import AuthClaims
from cys_core.domain.workers.models import JobResumeRequest
from cys_core.observability.http import mount_metrics
from cys_core.observability.metrics import metrics, seed_agent_trust_gauges
from cys_core.observability.platform_gauges import refresh_platform_gauges
from cys_core.observability.otel import instrument_fastapi, setup_otel
from interfaces.api.auth import require_ingress_role, require_operator_role, require_reader_role
from interfaces.api.tracing_middleware import tracing_middleware
from interfaces.api.task_supervisor import BackgroundTaskSupervisor
from interfaces.api.engagements import _latest_egress_phase
from interfaces.api.schemas import (
    InvestigationDetailOut,
    InvestigationJobsOut,
    InvestigationsListOut,
    InvestigationSummaryOut,
    JobSummaryOut,
)
from interfaces.control_plane.postgres_status_store import PostgresStatusStore
from interfaces.control_plane.status_store import MemoryStatusStore, get_status_store
from interfaces.ingress.router import EventIngress, get_event_ingress
from interfaces.worker.hitl_resume import HitlResumeError, resume_worker_job

import structlog

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
    from bootstrap.container import get_container

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
            while True:
                refresh_platform_gauges(
                    engagement_store=container.get_engagement_state_store(),
                    job_store=container.get_job_store(),
                )
                await asyncio.sleep(30)

        async def _reconcile_engagements_loop() -> None:
            container = get_container()
            reconciler = container.get_reconcile_stuck_engagements()
            while True:
                try:
                    await reconciler.execute()
                except Exception:
                    logger.exception("engagement_reconcile_loop_failed")
                await asyncio.sleep(300)

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
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def _tracing_middleware(request: Request, call_next):
        return await tracing_middleware(request, call_next)

    mount_metrics(app)
    instrument_fastapi(app)
    seed_agent_trust_gauges()

    from interfaces.api.catalog import router as catalog_router
    from interfaces.api.runs import router as runs_router
    from interfaces.api.engagements import router as engagements_router
    from interfaces.api.follow_ups import router as follow_ups_router
    from interfaces.api.work_orders import router as work_orders_router

    app.include_router(catalog_router)
    app.include_router(runs_router)
    app.include_router(work_orders_router)
    app.include_router(engagements_router)
    app.include_router(follow_ups_router)

    event_ingress = ingress or get_event_ingress()
    store = get_status_store()
    job_store = get_container().get_job_store()

    @app.post("/events", response_model=None)
    async def post_event(
        event_in: EventIn,
        request: Request,
        _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)],
    ) -> dict[str, Any] | JSONResponse:
        if get_settings().control_mode != "daemon":
            from interfaces.control_plane.coordinator_service import get_coordinator_service
            from interfaces.control_plane.critic_service import get_critic_service

            get_critic_service()
            get_coordinator_service()

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
        return {
            "status": "ok",
            **collect_infra_health(
                queue=container.get_job_queue(),
                egress=container.get_engagement_egress(),
                transport=get_bus_transport(),
                job_store=container.get_job_store(),
            ),
        }

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
            if isinstance(store, MemoryStatusStore):
                queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

                def on_event(_kind: str, event: dict[str, Any]) -> None:
                    queue.put_nowait(event)

                unsubscribe = store.subscribe(on_event)
                try:
                    while True:
                        try:
                            event = await asyncio.wait_for(queue.get(), timeout=15.0)
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
                    await asyncio.sleep(2)
            else:
                heartbeat = {"kind": "heartbeat", "ts": datetime.now(UTC).isoformat()}
                yield f"data: {json.dumps(heartbeat)}\n\n"
                await asyncio.sleep(15)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/investigations", response_model=InvestigationsListOut)
    async def list_investigations(
        tenant_id: str = "default",
        limit: int = 20,
        _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
    ) -> InvestigationsListOut:
        eng_store = get_container().get_engagement_state_store()
        engagements = eng_store.list_recent(tenant_id, limit=limit)
        return InvestigationsListOut(
            investigations=[
                InvestigationSummaryOut(
                    investigation_id=eng.id,
                    tenant_id=eng.tenant_id,
                    goal=eng.goal,
                    status=eng.status.value,
                    completed_personas=eng.completed_personas,
                )
                for eng in engagements
            ]
        )

    @app.get("/investigations/{investigation_id}", response_model=InvestigationDetailOut)
    async def get_investigation(
        investigation_id: str,
        tenant_id: str = "default",
        _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
    ) -> InvestigationDetailOut:
        eng_store = get_container().get_engagement_state_store()
        engagement = eng_store.get(tenant_id, investigation_id)
        if engagement is None:
            raise HTTPException(status_code=404, detail="Investigation not found")
        egress = get_container().get_engagement_egress()
        snapshot = getattr(egress, "snapshot", lambda *_a, **_k: [])(investigation_id, tenant_id=tenant_id)
        return InvestigationDetailOut(
            investigation_id=engagement.id,
            tenant_id=engagement.tenant_id,
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
        jobs = job_store.list_by_investigation(tenant_id, investigation_id)
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
                )
                for job in jobs
            ]
        )

    @app.get("/jobs/{job_id}")
    async def get_job(
        job_id: str,
        _auth: Annotated[AuthClaims | None, Depends(require_reader_role)],
    ) -> dict[str, Any]:
        record = job_store.get(job_id)
        if record is None:
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
        pending = job_store.list_pending_approvals()
        metrics.refresh_hitl_pending(len(pending))
        return {"count": len(pending), "approvals": [item.model_dump() for item in pending]}

    @app.post("/jobs/{job_id}/resume")
    async def resume_job(
        job_id: str,
        body: JobResumeRequest,
        _auth: Annotated[AuthClaims | None, Depends(require_operator_role)],
    ) -> dict[str, Any]:
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
