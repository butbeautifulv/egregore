from __future__ import annotations

import json
from typing import Any

from cys_core.application.ports.agent_runner import AgentRunner
from cys_core.application.ports.stream_context import StreamContext
from cys_core.application.runs.agent_run_kernel import AgentRunKernel
from cys_core.application.runs.kernel_mappers import worker_job_to_kernel_request
from cys_core.domain.parsing.json_text import parse_json_text
from cys_core.domain.workers.models import WorkerJob


class WorkerAgentExecutor:
    def __init__(
        self,
        *,
        runtime: AgentRunner,
        use_run_kernel: bool = False,
        self_refine_max: int = 0,
    ) -> None:
        self._runtime = runtime
        self._use_run_kernel = use_run_kernel
        self._self_refine_max = self_refine_max

    async def run(
        self,
        *,
        job: WorkerJob,
        sanitized: str,
        session_id: str,
        sandbox_tools: list,
        investigation_id: str,
        profile_id: str,
        sandbox_id: str,
        prior_findings_count: int,
    ) -> dict[str, Any]:
        if self._use_run_kernel and job.persona == "consultant":
            kernel = AgentRunKernel(self._runtime)
            request = worker_job_to_kernel_request(
                job,
                prompt=sanitized,
                session_id=session_id,
                profile_id=profile_id,
                sandbox_tools=sandbox_tools or None,
                memory_entries_loaded=prior_findings_count,
            )
            kernel_result = await kernel.execute(request)
            result = kernel_result.output
            if isinstance(result, dict) and kernel_result.trajectory.events:
                result = {**result, "_kernel_trajectory": kernel_result.trajectory.model_dump(mode="json")}
        else:
            stream_context = StreamContext(
                engagement_id=investigation_id,
                job_id=job.job_id,
                persona=job.persona,
                tenant_id=job.tenant_id,
            )
            result = await self._runtime.arun(
                job.persona,
                sanitized,
                session_id=session_id,
                sandbox_tools=sandbox_tools or None,
                job_id=job.job_id,
                event_id=job.event_id,
                correlation_id=job.correlation_id,
                tenant_id=job.tenant_id,
                investigation_id=investigation_id,
                sandbox_id=sandbox_id,
                stream_context=stream_context,
            )

        if isinstance(result, dict) and "raw_response" in result and "error" not in result:
            parsed = parse_json_text(str(result["raw_response"]))
            if parsed:
                result = parsed
        return result if isinstance(result, dict) else {"raw": result}

    async def self_refine(
        self,
        job: WorkerJob,
        sanitized: str,
        result: dict[str, Any],
        *,
        session_id: str = "",
    ) -> dict[str, Any]:
        max_rounds = self._self_refine_max
        if max_rounds <= 0 or not isinstance(result, dict) or "error" in result:
            return result
        budget_session = session_id or f"worker:{job.persona}:{job.job_id}"
        draft = json.dumps(result, ensure_ascii=False)
        rounds_done = 0
        for round_idx in range(max_rounds):
            rounds_done = round_idx + 1
            critique_prompt = (
                f"Critique this worker output for persona {job.persona}. "
                f"Input:\n{sanitized[:2000]}\nOutput:\n{draft[:4000]}\n"
                'Reply JSON: {"revise":true|false,"notes":"..."}'
            )
            revised = await self._runtime.arun(
                job.persona,
                critique_prompt,
                session_id=budget_session,
                tenant_id=job.tenant_id,
                investigation_id=job.correlation_id or job.event_id,
            )
            if not isinstance(revised, dict):
                break
            notes = str(revised.get("notes", revised.get("raw_response", "")))
            if not notes:
                break
            revise_prompt = f"Revise your prior output addressing: {notes}\nPrior:\n{draft[:4000]}"
            updated = await self._runtime.arun(
                job.persona,
                revise_prompt,
                session_id=budget_session,
                tenant_id=job.tenant_id,
                investigation_id=job.correlation_id or job.event_id,
            )
            if isinstance(updated, dict) and "error" not in updated:
                result = updated
                draft = json.dumps(result, ensure_ascii=False)
            else:
                break
        result["self_refine_rounds"] = rounds_done
        return result
