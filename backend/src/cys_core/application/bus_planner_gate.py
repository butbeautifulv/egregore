from cys_core.domain.engagement.bus_routing import (
    BUS_ALWAYS_RECIPIENTS,
    CONTROL_PLANE_RECIPIENTS,
    ControlPlaneMode,
    filter_bus_recipients_for_plan,
    filter_control_plane_recipients,
    filter_escalation_recipients,
    off_plan_bus_enqueue_reason,
)
from cys_core.domain.engagement.models import Engagement


def planner_personas_terminal(planner_plan: list[str], completed: list[str], failed: list[str]) -> bool:
    if not planner_plan:
        return False
    engagement = Engagement(
        id="synthetic",
        goal="",
        completed_personas=list(completed),
        failed_personas=list(failed),
    )
    return engagement.specialists_terminal(plan_personas=planner_plan)


__all__ = [
    "BUS_ALWAYS_RECIPIENTS",
    "CONTROL_PLANE_RECIPIENTS",
    "ControlPlaneMode",
    "filter_bus_recipients_for_plan",
    "filter_control_plane_recipients",
    "filter_escalation_recipients",
    "off_plan_bus_enqueue_reason",
    "planner_personas_terminal",
]
