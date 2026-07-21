from __future__ import annotations

from enum import Enum

from cys_core.domain.policy.defaults import ESCALATION_ONLY_PATHS

CONTROL_PLANE_RECIPIENTS = frozenset({"critic", "coordinator"})
BUS_ALWAYS_RECIPIENTS = CONTROL_PLANE_RECIPIENTS


class ControlPlaneMode(str, Enum):
    OFF = "off"
    GATE_ONLY = "gate_only"
    FULL = "full"


def _normalize_control_plane_mode(mode: str | ControlPlaneMode) -> str:
    if isinstance(mode, ControlPlaneMode):
        return mode.value
    return str(mode or ControlPlaneMode.GATE_ONLY.value)


def filter_control_plane_recipients(recipients: list[str], mode: str | ControlPlaneMode) -> list[str]:
    normalized = _normalize_control_plane_mode(mode)
    if normalized == ControlPlaneMode.OFF.value:
        return [recipient for recipient in recipients if recipient not in CONTROL_PLANE_RECIPIENTS]
    if normalized == ControlPlaneMode.GATE_ONLY.value:
        return [recipient for recipient in recipients if recipient != "coordinator"]
    return list(recipients)


def filter_bus_recipients_for_plan(
    recipients: list[str],
    planner_plan: list[str] | None,
    *,
    control_plane_mode: str | ControlPlaneMode = ControlPlaneMode.GATE_ONLY,
) -> list[str]:
    """Keep bus handoffs aligned with planner_plan; allow control-plane per profile mode."""
    recipients = filter_control_plane_recipients(recipients, control_plane_mode)
    planned = {persona for persona in (planner_plan or []) if persona}
    if not planned:
        return list(recipients)
    allow_control = _normalize_control_plane_mode(control_plane_mode) != ControlPlaneMode.OFF.value
    return [
        recipient
        for recipient in recipients
        if recipient in planned or (allow_control and recipient in CONTROL_PLANE_RECIPIENTS)
    ]


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
    escalation_paths: set[tuple[str, str]] | None = None,
) -> list[str]:
    """Drop privileged escalation paths unless message is critic-approved escalation.

    `escalation_paths` lets a caller pass the active profile's own paths (e.g.
    `SecureAgentBus.escalation_paths`, itself resolved from `ProfilePolicyPayload.
    escalation_paths`) instead of always using cybersec-soc's hardcoded pairs — see
    docs/MSP_BACKLOG.md §8.4 point 3. Defaults to `ESCALATION_ONLY_PATHS` unchanged for
    backward compatibility with any caller that doesn't pass one.
    """
    if msg_type == "escalation":
        return list(recipients)
    paths = ESCALATION_ONLY_PATHS if escalation_paths is None else escalation_paths
    blocked = {recipient for sender_name, recipient in paths if sender_name == sender}
    if not blocked:
        return list(recipients)
    return [recipient for recipient in recipients if recipient not in blocked]
