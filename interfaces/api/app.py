from __future__ import annotations

import cys_core.observability.prometheus_setup  # noqa: F401 — multiprocess atexit
import asyncio
import contextlib
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from bootstrap.container import get_container
from bootstrap.settings import get_settings
from cys_core.application.use_cases.async_manual_investigation import complete_manual_investigation_planning
from cys_core.application.use_cases.dispatch_event import ASYNC_PLANNER_PENDING
from cys_core.domain.security.auth_models import AuthClaims
from cys_core.domain.workers.models import JobResumeRequest
from cys_core.observability.http import mount_metrics
from cys_core.observability.metrics import metrics, seed_agent_trust_gauges
from cys_core.observability.platform_gauges import refresh_platform_gauges
from cys_core.observability.otel import instrument_fastapi, setup_otel
from interfaces.api.auth import require_ingress_role, require_operator_role, require_reader_role
from interfaces.api.schemas import (
    InvestigationDetailOut,
    InvestigationJobsOut,
    InvestigationsListOut,
    InvestigationSummaryOut,
    JobSummaryOut,
)
from interfaces.control_plane.job_store import get_job_store
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
    async def lifespan(_app: FastAPI):
        from cys_core.observability.logging_setup import configure_logging

        configure_logging("egregore-api")
        setup_otel(service_name="egregore-api")
        refresh_task: asyncio.Task[None] | None = None

        async def _refresh_gauges_loop() -> None:
            while True:
                refresh_platform_gauges()
                await asyncio.sleep(30)

        refresh_platform_gauges()
        refresh_task = asyncio.create_task(_refresh_gauges_loop())
        try:
            yield
        finally:
            if refresh_task is not None:
                refresh_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await refresh_task
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
    mount_metrics(app)
    instrument_fastapi(app)
    seed_agent_trust_gauges()

    from interfaces.api.catalog import router as catalog_router
    from interfaces.api.runs import router as runs_router

    app.include_router(catalog_router)
    app.include_router(runs_router)

    event_ingress = ingress or get_event_ingress()
    store = get_status_store()
    job_store = get_job_store()

    @app.post("/events")
    async def post_event(
        event_in: EventIn,
        _auth: Annotated[AuthClaims | None, Depends(require_ingress_role)],
    ) -> dict[str, Any]:
        if get_settings().control_mode != "daemon":
            from interfaces.control_plane.coordinator_service import get_coordinator_service
            from interfaces.control_plane.critic_service import get_critic_service

            get_critic_service()
            get_coordinator_service()
        event, decision, job_ids = await event_ingress.aingest(
            event_in.event_type,
            event_in.payload,
            severity=event_in.severity,
            source=event_in.source,
            event_id=event_in.event_id,
            correlation_id=event_in.correlation_id,
        )
        store.record_event(event.model_dump())

        if getattr(decision, "reason", None) == ASYNC_PLANNER_PENDING:
            planner = event_ingress.plan_investigation
            orchestrator = event_ingress.orchestrator

            async def _run_planner() -> None:
                try:
                    await complete_manual_investigation_planning(
                        event,
                        event_in.payload,
                        plan_investigation=planner,
                        enqueuer=orchestrator,
                        status_notifier=store if hasattr(store, "record_investigation_update") else None,
                    )
                except Exception:
                    logger.exception("Async planner failed for event %s", event.id)

            asyncio.create_task(_run_planner())
            body = {
                "event": event.model_dump(),
                "routing": decision.model_dump(),
                "job_ids": job_ids,
                "accepted": True,
                "planner_status": "planning",
            }
            return JSONResponse(status_code=202, content=body)

        return {
            "event": event.model_dump(),
            "routing": decision.model_dump(),
            "job_ids": job_ids,
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

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
        inv_store = get_container().get_investigation_state_store()
        states = inv_store.list_recent(tenant_id, limit=limit)
        return InvestigationsListOut(
            investigations=[
                InvestigationSummaryOut(
                    investigation_id=state.investigation_id,
                    tenant_id=state.tenant_id,
                    goal=state.goal,
                    status=state.status,
                    completed_personas=state.completed_personas,
                )
                for state in states
            ]
        )

    @app.get("/investigations/{investigation_id}", response_model=InvestigationDetailOut)
    async def get_investigation(
        investigation_id: str,
        tenant_id: str = "default",
        _auth: Annotated[AuthClaims | None, Depends(require_reader_role)] = None,
    ) -> InvestigationDetailOut:
        inv_store = get_container().get_investigation_state_store()
        state = inv_store.get(tenant_id, investigation_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Investigation not found")
        return InvestigationDetailOut(
            investigation_id=state.investigation_id,
            tenant_id=state.tenant_id,
            goal=state.goal,
            status=state.status,
            completed_personas=state.completed_personas,
            planner_plan=state.planner_plan,
            planner_status=state.planner_status,
            planner_rationale=state.planner_rationale,
            planner_error=state.planner_error,
            findings_summary=state.findings_summary,
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
        from interfaces.worker.orchestrator import WorkerOrchestrator

        result = await WorkerOrchestrator().process_next()
        if result is None:
            return {"status": "idle"}
        return {"status": "done", "result": result.model_dump()}

    return app
