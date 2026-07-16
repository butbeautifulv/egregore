from __future__ import annotations

import asyncio
from typing import Any

import structlog

from cys_core.application.bus_engagement import normalize_correlation_id
from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    get_tool_execution_count,
)
from cys_core.domain.workers.job_budget import JobBudgetTracker, configure_job_cost
from cys_core.domain.workers.models import RunResult
from cys_core.infrastructure.execution.envelope import SubprocessJobEnvelope
from cys_core.infrastructure.policy.budget_adapter import resolve_job_cost_context
from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id

logger = structlog.get_logger(__name__)


async def execute_sandboxed_job(
    envelope: SubprocessJobEnvelope,
    *,
    run_worker_job: Any,
    metrics: Any,
    tool_chain_policy: Any,
    job_timeout: float,
    soft_timeout: float,
    default_cost_rate: float,
) -> RunResult:
    """Run one budgeted job the way a `run-sandboxed-job` child process must:
    owning its own soft-timeout + salvage (Discovery A) and its own
    JobBudgetTracker/configure_job_cost lifecycle (Discovery D), since neither
    survives the parent/child process boundary. Mirrors
    WorkerOrchestrator.run_job's soft-timeout/salvage/finally logic, minus the
    Dispatcher-level concerns (dependency-deferral, budget enrichment) that
    already happened in the parent before this envelope was built.

    Split out from cmd_run_sandboxed_job so it's unit-testable with fakes
    instead of requiring a live container/Postgres catalog.
    """
    job, budgeted, session_id = envelope.job, envelope.budgeted, envelope.session_id

    profile_id, cost_rate = resolve_job_cost_context(budgeted, default_cost_rate=default_cost_rate)
    configure_job_cost(cost_rate, profile_id=profile_id)
    JobBudgetTracker.configure(
        session_id,
        max_tokens=budgeted.max_tokens,
        max_cost_usd=budgeted.max_cost_usd,
        max_tool_calls=budgeted.max_tool_calls,
        profile_id=profile_id,
    )

    investigation_id = normalize_correlation_id(job.correlation_id or job.event_id, job.payload)
    cid_token = bind_correlation_id(investigation_id)
    structlog.contextvars.bind_contextvars(
        persona=job.persona,
        job_id=job.job_id,
        correlation_id=investigation_id,
        work_kind=str(job.payload.get("work_kind", "")),
    )
    try:
        with metrics.track_worker_job(job.persona) as job_state:
            try:
                result = await asyncio.wait_for(
                    run_worker_job.execute(job, budgeted, session_id, job_state),
                    timeout=soft_timeout,
                )
            except TimeoutError:
                tool_count = get_tool_execution_count(job.job_id)
                salvaged: RunResult | None = None
                try:
                    salvaged = await run_worker_job.try_salvage_partial(
                        job, session_id, job_state, reason="soft_timeout"
                    )
                except Exception as exc:
                    logger.warning(
                        "sandboxed_job_soft_timeout_salvage_failed",
                        job_id=job.job_id,
                        persona=job.persona,
                        error=str(exc),
                    )
                if salvaged is not None:
                    logger.warning(
                        "sandboxed job soft-timeout salvaged",
                        job_id=job.job_id,
                        persona=job.persona,
                        tool_count=tool_count,
                        salvaged=True,
                    )
                    result = salvaged
                else:
                    logger.error(
                        "sandboxed job timed out",
                        job_id=job.job_id,
                        persona=job.persona,
                        timeout_s=job_timeout,
                        soft_timeout_s=soft_timeout,
                        tool_count=tool_count,
                        salvaged=False,
                    )
                    metrics.record_worker_job_timeout(job.persona)
                    await run_worker_job.mark_job_timeout(job)
                    result = RunResult(
                        job_id=job.job_id, persona=job.persona, success=False, error="worker_job_timeout"
                    )
            budget_state = JobBudgetTracker.get(session_id)
            if budget_state is not None:
                metrics.record_job_usage(
                    job.persona, tokens=budget_state.tokens_used, cost_usd=budget_state.cost_usd
                )
            return result
    finally:
        JobBudgetTracker.clear(session_id)
        clear_tool_execution_count(job.job_id)
        tool_chain_policy.clear(job.job_id)
        reset_correlation_id(cid_token)
        structlog.contextvars.unbind_contextvars("persona", "job_id", "correlation_id", "work_kind")
