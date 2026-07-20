from __future__ import annotations

import pytest

from cys_core.domain.runs.models import InteractionMode
from cys_core.domain.runs.state_models import RunStatus
from cys_core.domain.runs.status_policy import derive_run_status


@pytest.mark.unit
def test_derive_run_status_awaiting_user_from_status() -> None:
    assert derive_run_status({"status": "awaiting_user"}, mode=None) == RunStatus.AWAITING_USER


@pytest.mark.unit
def test_derive_run_status_awaiting_user_from_trace_escalation() -> None:
    result = {"trace_critic_escalation": True}
    assert derive_run_status(result, mode=InteractionMode.AGENT) == RunStatus.AWAITING_USER


@pytest.mark.unit
def test_derive_run_status_plan_mode() -> None:
    assert derive_run_status({}, mode=InteractionMode.PLAN) == RunStatus.AWAITING_PLAN_APPROVAL


@pytest.mark.unit
def test_derive_run_status_in_progress_default() -> None:
    assert derive_run_status({}, mode=InteractionMode.ASK) == RunStatus.IN_PROGRESS
