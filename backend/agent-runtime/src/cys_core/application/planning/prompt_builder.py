from __future__ import annotations

from cys_core.domain.catalog.models import PlannerPack, ProfilePack


class CatalogPlannerPromptBuilder:
    def __init__(self, *, profile: ProfilePack, planner: PlannerPack) -> None:
        self._profile = profile
        self._planner = planner

    def build(
        self,
        *,
        goal: str,
        event_type: str,
        severity: str,
        personas: list[str],
        max_personas: int,
        signals: dict[str, bool],
    ) -> str:
        template = (self._planner.prompt_template or _DEFAULT_TEMPLATE).strip()
        incident_hint = self._profile.incident_hint_template if signals.get("incident_id_present") else ""
        advisory_hint = self._profile.advisory_hint_template
        hints = (self._profile.hints_template or "").strip()
        if hints:
            hints = hints + "\n"
        return template.format(
            goal=goal,
            event_type=event_type,
            severity=severity,
            personas=", ".join(personas),
            max_personas=max_personas,
            incident_hint=incident_hint,
            advisory_hint=advisory_hint,
            hints=hints,
        )


_DEFAULT_TEMPLATE = """Goal: {goal}
Event type: {event_type}
Severity: {severity}
Available personas: {personas}
Select 1 to {max_personas} personas (minimal set). {incident_hint}{advisory_hint}{hints}\
For independent specialists use execution_mode parallel; use staged when order matters.
Specialist personas run first; consultant synthesis follows automatically after they finish \
(do not add consultant to the personas list)."""
