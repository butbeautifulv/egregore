from __future__ import annotations

from typing import Any

from cys_core.domain.engagement.models import Engagement, EngagementStatus, ExecutionMode, SynthesisStatus


def mark_persona_done(engagement: Engagement, persona: str) -> None:
    engagement.record_persona_completed(persona)


def mark_persona_failed(engagement: Engagement, persona: str) -> None:
    engagement.record_persona_failed(persona)


def append_finding(engagement: Engagement, finding: dict[str, Any]) -> None:
    persona = str(finding.get("persona", ""))
    job_id = str(finding.get("job_id", ""))
    if persona and job_id:
        for index, existing in enumerate(engagement.findings_summary):
            if (
                isinstance(existing, dict)
                and existing.get("persona") == persona
                and existing.get("job_id") == job_id
            ):
                engagement.findings_summary[index] = finding
                return
    engagement.findings_summary.append(finding)


def set_final_report(engagement: Engagement, report: dict[str, Any]) -> None:
    engagement.complete_synthesis(report)


def mark_synthesis_running(engagement: Engagement, job_id: str) -> None:
    engagement.synthesis_status = SynthesisStatus.RUNNING
    if job_id not in engagement.job_ids:
        engagement.job_ids.append(job_id)


def update_planner_state(
    engagement: Engagement,
    *,
    planner_plan: list[str] | None = None,
    planner_status: str | None = None,
    planner_rationale: str = "",
    planner_error: str = "",
    goal: str | None = None,
    execution_mode: str | None = None,
    synthesis_persona: str | None = None,
    planner_sub_goals: dict[str, str] | None = None,
    planner_depends_on: dict[str, list[str]] | None = None,
) -> None:
    mode = ExecutionMode(execution_mode) if execution_mode else None
    if planner_plan is not None:
        engagement.apply_planner_result(
            planner_plan,
            status=planner_status or engagement.planner_status or "planning",
            rationale=planner_rationale,
            error=planner_error,
            goal=goal,
            execution_mode=mode,
            synthesis_persona=synthesis_persona,
            planner_sub_goals=planner_sub_goals,
            planner_depends_on=planner_depends_on,
        )
    else:
        if planner_status is not None:
            engagement.planner_status = planner_status
        if planner_rationale:
            engagement.planner_rationale = planner_rationale
        if planner_error:
            engagement.planner_error = planner_error
        if goal is not None:
            engagement.goal = goal
        if execution_mode is not None:
            engagement.execution_mode = mode
        if synthesis_persona is not None:
            engagement.synthesis_persona = synthesis_persona
        if engagement.status == EngagementStatus.CREATED:
            engagement.begin_planning(goal=goal)


def fail_engagement(engagement: Engagement, *, reason: str) -> None:
    engagement.fail_guardrail(reason)


def fail_synthesis(engagement: Engagement, *, reason: str) -> None:
    specialist_findings = [
        item
        for item in engagement.findings_summary
        if isinstance(item, dict)
        and item.get("persona")
        and item.get("persona") != engagement.synthesis_persona
    ]
    engagement.fail_synthesis(reason, degraded=bool(specialist_findings))
