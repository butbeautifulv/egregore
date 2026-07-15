from __future__ import annotations

import json
import uuid
from typing import Any

import structlog

from cys_core.application.runtime_config import FollowUpSettings, get_follow_up_settings
from cys_core.application.follow_up.intent import classify_follow_up_mode, orchestrator_persona_for
from cys_core.application.operator_messages.service import (
    is_follow_up_turn_id,
    maybe_compact_context,
    persist_operator_turn_to_memory,
)
from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.application.ports.job_store import JobStorePort
from cys_core.application.ports.metrics import MetricsPort
from cys_core.domain.engagement.models import EngagementStatus, SynthesisStatus
from cys_core.domain.follow_up.models import FOLLOW_UP_PHASE, initial_follow_up_id
from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
from cys_core.domain.runs.models import ContextKind, InteractionMode, RunContext
from cys_core.domain.runs.state_models import RunState, RunStatus
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus

logger = structlog.get_logger(__name__)


class FollowUpError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class EnqueueFollowUp:
    def __init__(
        self,
        *,
        engagement_store: EngagementStateStore,
        memory_writer: MemoryWriteService,
        memory_reader: MemoryReadService,
        job_store: JobStorePort,
        queue: JobQueueConnector,
        run_state_store=None,
        engagement_egress: EngagementEgressPort | None = None,
        metrics: MetricsPort | None = None,
        follow_up_settings: FollowUpSettings | None = None,
    ) -> None:
        self._engagement_store = engagement_store
        self._memory_writer = memory_writer
        self._memory_reader = memory_reader
        self._job_store = job_store
        self._queue = queue
        self._run_state_store = run_state_store
        self._engagement_egress = engagement_egress
        self._metrics = metrics
        self._settings = follow_up_settings or get_follow_up_settings()

    def _ensure_run_context(self, tenant_id: str, engagement_id: str) -> None:
        if self._run_state_store is None:
            return
        existing = self._run_state_store.get(tenant_id, engagement_id, ContextKind.INVESTIGATION.value)
        if existing is not None:
            return
        ctx = RunContext(
            context_id=engagement_id,
            kind=ContextKind.INVESTIGATION,
            tenant_id=tenant_id,
            mode=InteractionMode.AGENT,
        )
        self._run_state_store.upsert(
            RunState(run_context=ctx, goal="", mode=InteractionMode.AGENT, status=RunStatus.IN_PROGRESS)
        )

    def _validate_engagement(self, tenant_id: str, engagement_id: str):
        engagement = self._engagement_store.get(tenant_id, engagement_id)
        if engagement is None:
            raise FollowUpError("engagement_not_found", status_code=404)
        if not self._settings.follow_up_enabled:
            raise FollowUpError("follow_up_disabled", status_code=503)
        if engagement.status == EngagementStatus.FAILED and not engagement.findings_summary:
            raise FollowUpError("engagement_failed_without_findings", status_code=409)
        if engagement.status not in (EngagementStatus.CLOSED,):
            raise FollowUpError("engagement_not_closed", status_code=409)
        if engagement.synthesis_status not in (SynthesisStatus.DONE, SynthesisStatus.SKIPPED, None):
            raise FollowUpError("synthesis_not_complete", status_code=409)
        turns = self._memory_reader.query_conversation_turns(
            tenant_id, engagement_id, limit=self._settings.follow_up_conversation_query_limit
        )
        operator_turns = [
            t for t in turns
            if self._turn_role(t) == "operator" and is_follow_up_turn_id(self._turn_follow_up_id(t))
        ]
        if len(operator_turns) >= self._settings.max_follow_ups_per_engagement:
            raise FollowUpError("follow_up_rate_limit", status_code=429)
        return engagement

    @staticmethod
    def _turn_follow_up_id(entry) -> str:
        try:
            data = json.loads(entry.content)
            return str(data.get("follow_up_id", ""))
        except json.JSONDecodeError:
            return ""

    @staticmethod
    def _turn_role(entry) -> str:
        try:
            data = json.loads(entry.content)
            return str(data.get("role", ""))
        except json.JSONDecodeError:
            return ""

    def _running_follow_up_job(self, tenant_id: str, engagement_id: str) -> str | None:
        for summary in self._job_store.list_by_investigation(tenant_id, engagement_id):
            if summary.status not in (WorkerJobStatus.PENDING, WorkerJobStatus.RUNNING):
                continue
            if "-fu-" in summary.job_id:
                return summary.job_id
        return None

    def persist_operator_turn(
        self,
        *,
        tenant_id: str,
        engagement_id: str,
        message: str,
        follow_up_id: str | None = None,
        work_kind: str = "",
        mode: str = "auto",
    ) -> tuple[str, Any]:
        engagement = self._validate_engagement(tenant_id, engagement_id)
        fu_id = follow_up_id or f"fu-{uuid.uuid4().hex[:12]}"
        try:
            persist_operator_turn_to_memory(
                self._memory_writer,
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                message=message,
                follow_up_id=fu_id,
                work_kind=work_kind,
                mode=mode,
                metrics=self._metrics,
                memory_reader=self._memory_reader,
                engagement_store=self._engagement_store,
            )
        except ValueError as exc:
            raise FollowUpError("conversation_turn_rejected", status_code=400) from exc
        return fu_id, engagement

    def _maybe_compact_context(self, tenant_id: str, engagement_id: str) -> None:
        maybe_compact_context(
            memory_reader=self._memory_reader,
            engagement_store=self._engagement_store,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
        )

    def enqueue_pending(
        self,
        *,
        tenant_id: str,
        engagement_id: str,
        follow_up_id: str,
        message: str,
        work_kind: str,
    ) -> dict[str, Any]:
        engagement = self._validate_engagement(tenant_id, engagement_id)
        if work_kind == "follow_up_orchestrate":
            engagement.follow_up_spawn_count = 0
            engagement.follow_up_spawned_job_ids = []
            self._engagement_store.upsert(engagement)
        running = self._running_follow_up_job(tenant_id, engagement_id)
        if running:
            pending = list(engagement.pending_follow_ups or [])
            pending.append({"follow_up_id": follow_up_id, "message": message.strip(), "work_kind": work_kind})
            engagement.pending_follow_ups = pending
            self._engagement_store.upsert(engagement)
            return {
                "follow_up_id": follow_up_id,
                "status": "pending",
                "work_kind": work_kind,
                "job_id": None,
            }
        persona = orchestrator_persona_for(work_kind)
        job_id = f"{persona}-fu-{uuid.uuid4().hex[:8]}"
        job = WorkerJob(
            job_id=job_id,
            event_id=engagement_id,
            persona=persona,
            correlation_id=engagement_id,
            tenant_id=tenant_id,
            payload={
                "phase": FOLLOW_UP_PHASE,
                "work_kind": work_kind,
                "operator_message": message.strip(),
                "follow_up_id": follow_up_id,
                "goal": engagement.goal,
                "context_id": engagement_id,
            },
        )
        self._ensure_run_context(tenant_id, engagement_id)
        self._job_store.upsert_pending(
            job.job_id,
            job.persona,
            correlation_id=job.correlation_id,
            tenant_id=job.tenant_id,
            event_id=job.event_id,
        )
        self._queue.enqueue(job)
        if self._metrics is not None:
            record = getattr(self._metrics, "record_follow_up_queued", None)
            if callable(record):
                record(work_kind)
        if self._engagement_egress is not None:
            self._engagement_egress.publish_event(
                engagement_id,
                "follow_up_queued",
                {
                    "tenant_id": tenant_id,
                    "follow_up_id": follow_up_id,
                    "work_kind": work_kind,
                    "job_id": job_id,
                },
            )
        return {
            "follow_up_id": follow_up_id,
            "status": "queued",
            "work_kind": work_kind,
            "job_id": job_id,
        }

    def execute(
        self,
        *,
        tenant_id: str,
        engagement_id: str,
        message: str,
        mode: str = "auto",
        enqueue: bool = True,
    ) -> dict[str, Any]:
        engagement = self._validate_engagement(tenant_id, engagement_id)
        turns = self._memory_reader.query_conversation_turns(
            tenant_id, engagement_id, limit=self._settings.follow_up_conversation_query_limit
        )
        prior_operator_turns = sum(1 for t in turns if self._turn_role(t) == "operator")
        work_kind = classify_follow_up_mode(
            message,
            mode=mode if mode in ("auto", "qa", "orchestrate", "plan") else "auto",
            prior_operator_turns=prior_operator_turns,
        )
        if work_kind == "follow_up_plan":
            if engagement.follow_up_iteration >= self._settings.max_follow_up_plans_per_engagement:
                raise FollowUpError("follow_up_plan_limit", status_code=429)
        fu_id, engagement = self.persist_operator_turn(
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            message=message,
            work_kind=work_kind,
            mode=mode,
        )
        if work_kind == "follow_up_orchestrate":
            engagement.follow_up_spawn_count = 0
            engagement.follow_up_spawned_job_ids = []
            self._engagement_store.upsert(engagement)
        if not enqueue:
            return {
                "follow_up_id": fu_id,
                "status": "persisted",
                "work_kind": work_kind,
                "job_id": None,
            }

        running = self._running_follow_up_job(tenant_id, engagement_id)
        if running:
            pending = list(engagement.pending_follow_ups or [])
            pending.append({"follow_up_id": fu_id, "message": message.strip(), "work_kind": work_kind})
            engagement.pending_follow_ups = pending
            self._engagement_store.upsert(engagement)
            return {
                "follow_up_id": fu_id,
                "status": "pending",
                "work_kind": work_kind,
                "job_id": None,
            }

        persona = orchestrator_persona_for(work_kind)
        job_id = f"{persona}-fu-{uuid.uuid4().hex[:8]}"
        job = WorkerJob(
            job_id=job_id,
            event_id=engagement_id,
            persona=persona,
            correlation_id=engagement_id,
            tenant_id=tenant_id,
            payload={
                "phase": FOLLOW_UP_PHASE,
                "work_kind": work_kind,
                "operator_message": message.strip(),
                "follow_up_id": fu_id,
                "goal": engagement.goal,
                "context_id": engagement_id,
            },
        )
        self._ensure_run_context(tenant_id, engagement_id)
        self._job_store.upsert_pending(
            job.job_id,
            job.persona,
            correlation_id=job.correlation_id,
            tenant_id=job.tenant_id,
            event_id=job.event_id,
        )
        self._queue.enqueue(job)
        if self._metrics is not None:
            record = getattr(self._metrics, "record_follow_up_queued", None)
            if callable(record):
                record(work_kind)
        if self._engagement_egress is not None:
            self._engagement_egress.publish_event(
                engagement_id,
                "follow_up_queued",
                {
                    "tenant_id": tenant_id,
                    "follow_up_id": fu_id,
                    "work_kind": work_kind,
                    "job_id": job_id,
                },
            )
        logger.info(
            "follow_up_enqueued",
            engagement_id=engagement_id,
            follow_up_id=fu_id,
            work_kind=work_kind,
            job_id=job_id,
        )
        return {
            "follow_up_id": fu_id,
            "status": "queued",
            "work_kind": work_kind,
            "job_id": job_id,
        }

    def list_turns(self, tenant_id: str, engagement_id: str) -> list[dict[str, Any]]:
        entries = self._memory_reader.query_conversation_turns(
            tenant_id, engagement_id, limit=self._settings.follow_up_history_limit
        )
        turns: list[dict[str, Any]] = []
        has_initial = False
        for entry in entries:
            try:
                data = json.loads(entry.content)
            except json.JSONDecodeError:
                data = {"role": "unknown", "text": entry.content, "follow_up_id": ""}
            follow_up_id = str(data.get("follow_up_id", ""))
            if follow_up_id == initial_follow_up_id(engagement_id):
                has_initial = True
            turns.append(
                {
                    "id": entry.id,
                    "role": str(data.get("role", "unknown")),
                    "text": str(data.get("text", "")),
                    "created_at": entry.created_at.isoformat(),
                    "follow_up_id": follow_up_id,
                    "job_id": data.get("job_id"),
                    "persona": data.get("persona"),
                    "status": str(data.get("status", "completed")),
                    "work_kind": data.get("work_kind"),
                    "mode": data.get("mode"),
                    "content_type": data.get("content_type"),
                    "finding": data.get("finding"),
                }
            )
        if not has_initial:
            engagement = self._engagement_store.get(tenant_id, engagement_id)
            goal = (engagement.goal or "").strip() if engagement is not None else ""
            if goal:
                created_at = ""
                if engagement is not None and getattr(engagement, "planning_started_at", None):
                    created_at = str(engagement.planning_started_at)
                if not created_at and engagement is not None:
                    created_at = str(getattr(engagement, "updated_at", "") or "")
                if not created_at:
                    from datetime import datetime, timezone

                    created_at = datetime.now(timezone.utc).isoformat()
                turns.insert(
                    0,
                    {
                        "id": f"synthetic-{engagement_id}",
                        "role": "operator",
                        "text": goal,
                        "created_at": created_at,
                        "follow_up_id": initial_follow_up_id(engagement_id),
                        "job_id": None,
                        "persona": None,
                        "status": "completed",
                        "work_kind": None,
                        "mode": "auto",
                        "content_type": None,
                        "finding": None,
                    },
                )
        turns.sort(key=lambda item: item.get("created_at", ""))
        return turns
