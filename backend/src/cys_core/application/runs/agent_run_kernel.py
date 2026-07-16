from __future__ import annotations

from typing import Any, Protocol

from cys_core.application.runs.kernel_budget import kernel_budget
from cys_core.application.runs.kernel_mappers import new_trajectory
from cys_core.application.runs.kernel_memory import record_memory_read
from cys_core.application.runs.kernel_tool_capture import capture_tool_traces
from cys_core.domain.runs.kernel_models import RunKernelRequest, RunKernelResult
from cys_core.domain.runs.trace_models import ModelCallTraceFields, model_call_trace
from cys_core.domain.workers.job_budget import JobBudgetTracker


class KernelRuntime(Protocol):
    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        sandbox_tools: list[Any] | None = None,
        job_id: str | None = None,
        event_id: str | None = None,
        correlation_id: str | None = None,
        tenant_id: str | None = None,
        investigation_id: str | None = None,
        sandbox_id: str | None = None,
        profile_id: str | None = None,
    ) -> dict[str, Any]: ...


class AgentRunKernel:
    """Default RunKernelPort: budget + runtime.arun + trajectory capture."""

    def __init__(self, runtime: KernelRuntime) -> None:
        self._runtime = runtime

    async def execute(self, request: RunKernelRequest) -> RunKernelResult:
        trajectory = new_trajectory(request)
        record_memory_read(trajectory, request, entries=request.memory_entries_loaded)
        with kernel_budget(request):
            output = await self._runtime.arun(
                request.persona,
                request.prompt,
                session_id=request.session_id,
                sandbox_tools=request.sandbox_tools,
                job_id=request.job_id,
                event_id=request.event_id,
                correlation_id=request.correlation_id or request.investigation_id,
                tenant_id=request.tenant_id,
                investigation_id=request.investigation_id,
                sandbox_id=request.sandbox_id,
                profile_id=request.profile_id,
            )
            budget = JobBudgetTracker.get(request.session_id)
            if budget is not None:
                trajectory.record(
                    model_call_trace(
                        request.persona,
                        ModelCallTraceFields(
                            model=request.persona,
                            tokens_in=0,
                            tokens_out=budget.tokens_used,
                            cost_usd=budget.cost_usd,
                        ),
                    )
                )
        if isinstance(output, dict):
            capture_tool_traces(output, trajectory)
        success = isinstance(output, dict) and "error" not in output
        error = str(output.get("error", "")) if isinstance(output, dict) else ""
        return RunKernelResult(
            success=success,
            output=output if isinstance(output, dict) else {"raw": output},
            trajectory=trajectory,
            error=error,
        )
