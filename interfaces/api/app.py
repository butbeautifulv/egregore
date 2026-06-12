from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from bootstrap.settings import get_settings
from cys_core.domain.workers.models import JobResumeRequest
from cys_core.observability.http import mount_metrics
from cys_core.observability.metrics import metrics, seed_agent_trust_gauges
from interfaces.control_plane.job_store import get_job_store
from interfaces.control_plane.status_store import get_status_store
from interfaces.ingress.router import EventIngress, get_event_ingress
from interfaces.worker.hitl_resume import HitlResumeError, resume_worker_job


class EventIn(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    severity: str = "medium"
    source: str = ""
    event_id: str | None = None
    correlation_id: str = ""


def create_app(ingress: EventIngress | None = None) -> FastAPI:
    """FastAPI app for event ingest and user status."""
    app = FastAPI(title="cys-agi event platform", version="0.2.0")
    mount_metrics(app)
    seed_agent_trust_gauges()
    event_ingress = ingress or get_event_ingress()
    store = get_status_store()
    job_store = get_job_store()

    @app.post("/events")
    async def post_event(event_in: EventIn) -> dict[str, Any]:
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
        return {
            "event": event.model_dump(),
            "routing": decision.model_dump(),
            "job_ids": job_ids,
        }

    @app.get("/status")
    async def get_status() -> dict[str, Any]:
        return store.snapshot()

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
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
    async def list_pending_approvals() -> dict[str, Any]:
        pending = job_store.list_pending_approvals()
        metrics.refresh_hitl_pending(len(pending))
        return {"count": len(pending), "approvals": [item.model_dump() for item in pending]}

    @app.post("/jobs/{job_id}/resume")
    async def resume_job(job_id: str, body: JobResumeRequest) -> dict[str, Any]:
        try:
            return await resume_worker_job(job_id, body)
        except HitlResumeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/workers/process-one")
    async def process_one_worker() -> dict[str, Any]:
        from interfaces.worker.orchestrator import WorkerOrchestrator

        result = await WorkerOrchestrator().process_next()
        if result is None:
            return {"status": "idle"}
        return {"status": "done", "result": result.model_dump()}

    return app
