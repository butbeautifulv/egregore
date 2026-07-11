from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from cys_core.application.ports.job_store import JobStorePort
from cys_core.domain.memory.services import MemoryReadService
from cys_core.domain.workers.models import WorkerJobStatus


class FollowUpAggregator:
    """Wait for spawned follow-up child jobs and merge their outputs into the orchestrator answer."""

    def __init__(
        self,
        job_store: JobStorePort,
        *,
        memory_reader: MemoryReadService | None = None,
        engagement_store: Any | None = None,
    ) -> None:
        self._job_store = job_store
        self._memory_reader = memory_reader
        self._engagement_store = engagement_store

    def spawned_child_ids(self, tenant_id: str, investigation_id: str, *, orchestrator_job_id: str) -> list[str]:
        del orchestrator_job_id
        if self._engagement_store is None:
            return []
        engagement = self._engagement_store.get(tenant_id, investigation_id)
        if engagement is None:
            return []
        return list(engagement.follow_up_spawned_job_ids or [])

    async def wait_for_children(
        self,
        child_ids: list[str],
        *,
        timeout_s: float = 300.0,
        poll_s: float = 2.0,
    ) -> bool:
        if not child_ids:
            return True
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if all(self._is_terminal(job_id) for job_id in child_ids):
                return True
            await asyncio.sleep(poll_s)
        return all(self._is_terminal(job_id) for job_id in child_ids)

    def _is_terminal(self, job_id: str) -> bool:
        record = self._job_store.get(job_id)
        if record is None:
            return True
        return record.status in (WorkerJobStatus.COMPLETED, WorkerJobStatus.FAILED)

    def merge_child_findings(
        self,
        result: dict[str, Any],
        child_ids: list[str],
        *,
        tenant_id: str,
        investigation_id: str,
    ) -> dict[str, Any]:
        if not child_ids:
            return result
        lines: list[str] = []
        for job_id in child_ids:
            record = self._job_store.get(job_id)
            if record is None:
                continue
            lines.append(f"{record.persona} ({job_id}): {record.status.value}")
        if self._memory_reader is not None:
            for entry in self._memory_reader.query_investigation(tenant_id, investigation_id, limit=30):
                if entry.source_job_id not in child_ids:
                    continue
                if entry.memory_type not in ("finding", "pending_finding"):
                    continue
                try:
                    finding = json.loads(entry.content)
                    summary = finding.get("summary") or finding.get("answer") or entry.content[:400]
                except json.JSONDecodeError:
                    summary = entry.content[:400]
                lines.append(f"{entry.source_agent}: {summary}")
        if not lines:
            return result
        base = str(result.get("answer") or result.get("summary") or "").strip()
        merged = base
        if merged:
            merged += "\n\n"
        merged += "Specialist follow-up results:\n" + "\n".join(f"- {line}" for line in lines)
        return {**result, "answer": merged, "summary": merged}
