from __future__ import annotations

from typing import Any

from cys_core.domain.runs.models import InteractionMode
from cys_core.domain.runs.state_models import RunStatus


def derive_run_status(result: dict[str, Any], *, mode: InteractionMode | None) -> RunStatus:
    if result.get("status") == "awaiting_user":
        return RunStatus.AWAITING_USER
    if result.get("trace_critic_escalation"):
        return RunStatus.AWAITING_USER
    if mode == InteractionMode.PLAN:
        return RunStatus.AWAITING_PLAN_APPROVAL
    return RunStatus.IN_PROGRESS
