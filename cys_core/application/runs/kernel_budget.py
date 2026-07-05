from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from cys_core.application.runs.budget_metrics import _metrics
from cys_core.application.runs.run_budget import run_session_budget
from cys_core.domain.runs.kernel_models import RunKernelRequest
from cys_core.domain.workers.budgets import persona_budget
from cys_core.domain.workers.job_budget import JobBudgetTracker


@contextmanager
def kernel_budget(request: RunKernelRequest) -> Iterator[None]:
    """Configure per-run budget from kernel request (interactive or worker)."""
    max_tokens = request.max_tokens
    max_cost = request.max_cost_usd
    max_tools = request.max_tool_calls
    if max_tokens is None or max_cost is None or max_tools is None:
        budget = persona_budget(request.persona)
        max_tokens = max_tokens if max_tokens is not None else budget.max_tokens
        max_cost = max_cost if max_cost is not None else budget.max_cost_usd
        max_tools = max_tools if max_tools is not None else budget.max_tool_calls
    JobBudgetTracker.configure(
        request.session_id,
        max_tokens=max_tokens,
        max_cost_usd=max_cost,
        max_tool_calls=max_tools,
        profile_id=request.profile_id,
    )
    try:
        yield
    finally:
        state = JobBudgetTracker.get(request.session_id)
        if state is not None:
            _metrics().record_job_usage(
                request.persona,
                tokens=state.tokens_used,
                cost_usd=state.cost_usd,
            )
        JobBudgetTracker.clear(request.session_id)


@contextmanager
def kernel_interactive_budget(request: RunKernelRequest) -> Iterator[None]:
    """Interactive runs reuse run_session_budget (persona defaults)."""
    with run_session_budget(request.session_id, request.persona):
        yield
