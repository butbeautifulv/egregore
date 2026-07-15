from __future__ import annotations

import re
from typing import Literal

from bootstrap.settings import get_settings
from cys_core.domain.follow_up.models import FollowUpMode

_REINVESTIGATE_PATTERNS = (
    re.compile(r"проверь (ещё|еще|снова|повторно)", re.IGNORECASE),
    re.compile(r"дополни расследование", re.IGNORECASE),
    re.compile(r"re-?investigate", re.IGNORECASE),
    re.compile(r"посмотри (на|в) (siem|лог)", re.IGNORECASE),
    re.compile(r"check (again|the logs)", re.IGNORECASE),
)

OperatorContext = Literal["initial", "follow_up"]


def classify_operator_intent(
    message: str,
    *,
    mode: FollowUpMode = "auto",
    context: OperatorContext = "follow_up",
    prior_operator_turns: int = 0,
) -> str:
    if context == "initial":
        if mode == "qa":
            return "initial_qa"
        if mode == "orchestrate":
            mode = "plan"  # v1 coerce
        return classify_follow_up_mode(message, mode=mode, prior_operator_turns=0)
    return classify_follow_up_mode(message, mode=mode, prior_operator_turns=prior_operator_turns)


def classify_follow_up_mode(
    message: str,
    *,
    mode: FollowUpMode = "auto",
    prior_operator_turns: int = 0,
) -> str:
    """Return follow_up work_kind string."""
    settings = get_settings()
    plan_enabled = getattr(settings, "follow_up_plan_enabled", False)

    if mode == "plan" and plan_enabled:
        return "follow_up_plan"
    if mode == "qa":
        return "follow_up_qa"
    if mode == "orchestrate":
        return "follow_up_orchestrate"

    if prior_operator_turns == 0 and plan_enabled:
        return "follow_up_plan"

    text = message.strip()
    for pattern in _REINVESTIGATE_PATTERNS:
        if pattern.search(text):
            return "follow_up_orchestrate"
    return "follow_up_qa"


def orchestrator_persona_for(work_kind: str) -> str:
    if work_kind == "follow_up_orchestrate":
        return "conductor"
    if work_kind == "follow_up_plan":
        return "planner"
    return "consultant"
