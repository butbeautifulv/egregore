from __future__ import annotations

import pytest

from cys_core.domain.runs.models import InteractionMode, RunContext
from cys_core.domain.runs.state_models import RunState, RunStatus


@pytest.mark.unit
def test_run_state_defaults():
    ctx = RunContext.from_session_id("s1", mode=InteractionMode.PLAN)
    state = RunState(run_context=ctx, goal="g")
    assert state.status == RunStatus.OPEN
    assert state.mode is None


@pytest.mark.unit
def test_run_status_values():
    assert RunStatus.AWAITING_PLAN_APPROVAL.value == "awaiting_plan_approval"
    assert RunStatus.CLOSED.value == "closed"
