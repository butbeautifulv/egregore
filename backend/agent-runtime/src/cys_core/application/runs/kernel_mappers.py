from __future__ import annotations

import uuid

from cys_core.domain.runs.checkpoint import checkpoint_key
from cys_core.domain.runs.kernel_models import RunKernelMode, RunKernelRequest
from cys_core.domain.runs.models import RunContext
from cys_core.domain.runs.state_models import RunState
from cys_core.domain.runs.trajectory import AgentTrajectory
from cys_core.domain.workers.budgets import persona_budget
from cys_core.domain.workers.models import WorkerJob


def new_trajectory(request: RunKernelRequest) -> AgentTrajectory:
    return AgentTrajectory(
        trajectory_id=f"traj-{request.run_id}",
        context_id=request.investigation_id or request.run_id,
        tenant_id=request.tenant_id,
        profile_id=request.profile_id,
        persona=request.persona,
        correlation_id=request.correlation_id or request.investigation_id,
        run_id=request.run_id,
    )


def run_state_to_kernel_request(
    *,
    state: RunState,
    ctx: RunContext,
    user_input: str,
    persona: str,
    prompt: str,
) -> RunKernelRequest:
    session_id = checkpoint_key(ctx, persona=persona)
    budget = persona_budget(persona)
    return RunKernelRequest(
        run_id=ctx.context_id,
        session_id=session_id,
        persona=persona,
        profile_id=ctx.profile_id,
        tenant_id=ctx.tenant_id,
        investigation_id=ctx.context_id,
        correlation_id=ctx.correlation_key,
        prompt=prompt,
        mode=RunKernelMode.INTERACTIVE,
        max_tokens=budget.max_tokens,
        max_cost_usd=budget.max_cost_usd,
        max_tool_calls=budget.max_tool_calls,
    )


def worker_job_to_kernel_request(
    job: WorkerJob,
    *,
    prompt: str,
    session_id: str,
    profile_id: str,
    sandbox_tools: list | None = None,
    memory_entries_loaded: int = 0,
) -> RunKernelRequest:
    investigation_id = job.correlation_id or job.event_id
    budget = persona_budget(job.persona)
    return RunKernelRequest(
        run_id=job.job_id,
        session_id=session_id,
        persona=job.persona,
        profile_id=profile_id,
        tenant_id=job.tenant_id,
        investigation_id=investigation_id,
        correlation_id=investigation_id,
        prompt=prompt,
        mode=RunKernelMode.WORKER,
        max_tokens=job.max_tokens or budget.max_tokens,
        max_cost_usd=job.max_cost_usd or budget.max_cost_usd,
        max_tool_calls=job.max_tool_calls or budget.max_tool_calls,
        sandbox_tools=sandbox_tools,
        job_id=job.job_id,
        event_id=job.event_id,
        sandbox_id=job.sandbox_id or None,
        memory_entries_loaded=memory_entries_loaded,
    )


def ephemeral_trajectory_id() -> str:
    return f"traj-{uuid.uuid4().hex[:12]}"
