from __future__ import annotations

import uuid
from typing import Any, Literal

FollowUpWorkKind = Literal[
    "follow_up_qa",
    "follow_up_orchestrate",
    "follow_up_child",
    "follow_up_plan",
    "initial_qa",
]
FollowUpMode = Literal["auto", "qa", "orchestrate", "plan"]
OperatorIntentMode = FollowUpMode

FOLLOW_UP_PHASE = "follow_up"
INITIAL_WORK_KINDS = frozenset({"initial_qa"})
FOLLOW_UP_WORK_KINDS = frozenset(
    {"follow_up_qa", "follow_up_orchestrate", "follow_up_child", "follow_up_plan", "initial_qa"}
)


def initial_follow_up_id(engagement_id: str) -> str:
    return f"wo-{engagement_id}"


def new_follow_up_id() -> str:
    """Random id for a follow-up turn.

    The 12-hex-char suffix must never be all-digits: it gets embedded verbatim in
    memory content (see MemoryWriteService.append_conversation_turn) that later
    passes through RedactionService.redact_pii(), whose RU-INN pattern is a bare
    `\\b(?:\\d{10}|\\d{12})\\b` with no checksum check — an unlucky all-digit uuid4
    hex draw (~0.75% of the time) gets silently mangled into "fu-[INN_REDACTED]",
    corrupting the id used to correlate this turn (docs/MICROSERVICES_SPLIT_PLAN.md).
    """
    suffix = uuid.uuid4().hex[:12]
    if suffix.isdigit():
        suffix = suffix[:-1] + "f"
    return f"fu-{suffix}"


def work_kind_from_payload(payload: dict[str, Any]) -> str:
    return str(payload.get("work_kind", "")).strip()


def is_initial_qa_payload(payload: dict[str, Any]) -> bool:
    return work_kind_from_payload(payload) == "initial_qa"


def is_follow_up_payload(payload: dict[str, Any]) -> bool:
    return payload.get("phase") == FOLLOW_UP_PHASE or work_kind_from_payload(payload) in FOLLOW_UP_WORK_KINDS


def is_follow_up_orchestrator(payload: dict[str, Any]) -> bool:
    kind = work_kind_from_payload(payload)
    return kind in ("follow_up_qa", "follow_up_orchestrate", "initial_qa")


def is_follow_up_planning(payload: dict[str, Any]) -> bool:
    return work_kind_from_payload(payload) == "follow_up_plan"


def is_follow_up_plan_iteration(payload: dict[str, Any]) -> bool:
    """Specialist jobs spawned during a follow-up catalog re-plan."""
    if not is_follow_up_planning(payload):
        return False
    return payload.get("phase") != "synthesis"


def is_follow_up_plan_planner_job(payload: dict[str, Any], *, persona: str) -> bool:
    return is_follow_up_planning(payload) and persona == "planner"
