from __future__ import annotations

import logging
from typing import Any, Callable

from cys_core.domain.engagement.models import EngagementPlan, ExecutionMode

logger = logging.getLogger(__name__)

Processor = Callable[[EngagementPlan, dict[str, Any], list[str], str], EngagementPlan]


def advisory_consultant_fallback(
    plan: EngagementPlan,
    ctx: dict[str, Any],
    available: list[str],
    goal: str,
) -> EngagementPlan:
    if plan.personas or "consultant" not in set(available):
        return plan
    if not ctx.get("advisory"):
        return plan
    logger.warning("planner empty personas; advisory fallback to consultant for goal=%r", goal[:120])
    plan.personas = ["consultant"]
    plan.sub_goals = {"consultant": goal}
    if not plan.rationale:
        plan.rationale = "Advisory goal — defaulted to consultant after empty planner personas."
    return plan


def staged_soc_intel_for_incident(
    plan: EngagementPlan, ctx: dict[str, Any], available: list[str], goal: str
) -> EngagementPlan:
    del goal
    if not ctx.get("incident_id_present"):
        return plan
    if plan.personas != ["soc"]:
        return plan
    if "intel" not in set(available):
        return plan
    plan.personas = ["soc", "intel"]
    plan.execution_mode = ExecutionMode.STAGED
    if "intel" not in plan.sub_goals:
        plan.sub_goals["intel"] = plan.sub_goals.get("soc", "")
    return plan


_PROCESSORS: dict[str, Processor] = {
    "advisory_consultant_fallback": advisory_consultant_fallback,
    "staged_soc_intel_for_incident": staged_soc_intel_for_incident,
}


def apply_post_processors(
    plan: EngagementPlan,
    processor_names: list[str],
    *,
    signals: dict[str, bool],
    available: list[str],
    goal: str,
) -> EngagementPlan:
    ctx = dict(signals)
    for name in processor_names:
        processor = _PROCESSORS.get(name)
        if processor is None:
            continue
        plan = processor(plan, ctx, available, goal)
    return plan
