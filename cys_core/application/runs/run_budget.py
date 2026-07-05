from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from cys_core.application.runs.budget_metrics import _metrics
from cys_core.domain.workers.budgets import persona_budget
from cys_core.domain.workers.job_budget import JobBudgetTracker


@contextmanager
def run_session_budget(session_id: str, persona: str) -> Iterator[None]:
    """Configure DoW budget for conductor / gaia_solver interactive runs."""
    budget = persona_budget(persona)
    JobBudgetTracker.configure(
        session_id,
        max_tokens=budget.max_tokens,
        max_cost_usd=budget.max_cost_usd,
        max_tool_calls=budget.max_tool_calls,
    )
    try:
        yield
    finally:
        state = JobBudgetTracker.get(session_id)
        if state is not None:
            _metrics().record_job_usage(
                persona,
                tokens=state.tokens_used,
                cost_usd=state.cost_usd,
            )
        JobBudgetTracker.clear(session_id)


@contextmanager
def nested_delegate_budget(parent_session_id: str, child_session_id: str, *, fraction: float = 0.35) -> Iterator[None]:
    """Sub-budget for in-process delegate_research calls."""
    parent = JobBudgetTracker.get(parent_session_id)
    if parent is None:
        yield
        return
    remaining_tools = max(1, parent.max_tool_calls - parent.tool_calls)
    remaining_tokens = max(1000, parent.max_tokens - parent.tokens_used)
    JobBudgetTracker.configure(
        child_session_id,
        max_tokens=max(1000, int(remaining_tokens * fraction)),
        max_cost_usd=max(0.05, parent.max_cost_usd * fraction),
        max_tool_calls=max(1, int(remaining_tools * fraction)),
    )
    try:
        yield
    finally:
        JobBudgetTracker.clear(child_session_id)
