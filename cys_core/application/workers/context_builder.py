from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.domain.memory.services import MemoryReadService
from cys_core.domain.workers.models import WorkerJob


class WorkerContextBuilder:
    def __init__(
        self,
        *,
        engagement_store: EngagementStateStore | None = None,
        memory_reader: MemoryReadService | None = None,
        record_memory_read: Callable[[str, int], None] | None = None,
    ) -> None:
        self._engagement_store = engagement_store
        self._memory_reader = memory_reader
        self._record_memory_read = record_memory_read or (lambda _tenant, _count: None)

    def investigation_id(self, job: WorkerJob) -> str:
        parent_key = job.payload.get("parent_correlation_key")
        if parent_key:
            return str(parent_key)
        return job.correlation_id or job.event_id

    def build(self, job: WorkerJob) -> dict[str, Any]:
        investigation_id = self.investigation_id(job)
        context: dict[str, Any] = {"investigation_id": investigation_id, "tenant_id": job.tenant_id}
        if self._engagement_store is not None:
            engagement = self._engagement_store.get(job.tenant_id, investigation_id)
            if engagement is not None:
                context["state"] = engagement.model_dump(mode="json")
        if self._memory_reader is not None:
            entries = self._memory_reader.query_investigation(
                job.tenant_id,
                investigation_id,
                limit=10,
                requesting_tenant_id=job.tenant_id,
            )
            if entries:
                self._record_memory_read(job.tenant_id, len(entries))
                context["prior_findings"] = [
                    {
                        "agent": entry.source_agent,
                        "type": entry.memory_type,
                        "content": entry.content,
                        "job_id": entry.source_job_id,
                    }
                    for entry in entries
                ]
        return context

    def job_input(self, job: WorkerJob) -> str:
        sub_goals = job.payload.get("sub_goals", {})
        if not isinstance(sub_goals, dict):
            sub_goals = {}
        engagement = (
            self._engagement_store.get(job.tenant_id, self.investigation_id(job))
            if self._engagement_store is not None
            else None
        )
        goal = str(job.payload.get("goal", job.payload.get("message", "")))
        if engagement is not None and engagement.goal:
            goal = engagement.goal
        return json.dumps(
            {
                "persona": job.persona,
                "goal": goal,
                "sub_goal": str(sub_goals.get(job.persona, "")),
                "planner_plan": job.payload.get("planner_plan", []),
                "event_id": job.event_id,
                "playbook_id": job.playbook_id,
                "payload": job.payload,
                "sandbox_id": job.sandbox_id,
                "feedback": job.feedback,
                "investigation_context": self.build(job),
            },
            ensure_ascii=False,
        )
