from __future__ import annotations

from cys_core.domain.policy.defaults import ESCALATION_ONLY_PATHS

CONTROL_PLANE_RECIPIENTS = frozenset({"critic", "coordinator"})
BUS_ALWAYS_RECIPIENTS = CONTROL_PLANE_RECIPIENTS


def filter_bus_recipients_for_plan(recipients: list[str], planner_plan: list[str] | None) -> list[str]:
    """Keep bus handoffs aligned with planner_plan; always allow control-plane recipients."""
    planned = {persona for persona in (planner_plan or []) if persona}
    if not planned:
        return list(recipients)
    return [recipient for recipient in recipients if recipient in planned or recipient in CONTROL_PLANE_RECIPIENTS]


def off_plan_bus_enqueue_reason(
    recipient: str,
    planner_plan: list[str] | None,
    *,
    msg_type: str,
) -> str | None:
    """Return rejection reason when a bus job targets a persona outside planner_plan."""
    planned = {persona for persona in (planner_plan or []) if persona}
    if not planned:
        return None
    if recipient in CONTROL_PLANE_RECIPIENTS:
        return None
    if msg_type == "revision":
        if recipient in planned:
            return None
        return "revision_off_plan"
    if msg_type in ("finding", "delegate"):
        if recipient in planned:
            return None
        return "finding_off_plan"
    return None


def filter_escalation_recipients(
    sender: str,
    recipients: list[str],
    *,
    msg_type: str = "finding",
) -> list[str]:
    """Drop privileged escalation paths unless message is critic-approved escalation."""
    if msg_type == "escalation":
        return list(recipients)
    blocked = {recipient for sender_name, recipient in ESCALATION_ONLY_PATHS if sender_name == sender}
    if not blocked:
        return list(recipients)
    return [recipient for recipient in recipients if recipient not in blocked]
