from __future__ import annotations

from pathlib import Path

from cys_core.application.plans.plan_loader import load_plans_from_dir
from cys_core.application.ports.profile_policy import ProfilePolicyPort
from cys_core.application.ports.registry_catalogs import PlanCatalogPort
from cys_core.application.runtime_config import get_use_dynamic_catalog
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.events.models import RoutingDecision, SecurityEvent
from cys_core.domain.events.plans import PlanRoutingConfig, parse_rule, rule_matches


class EventRouter:
    """Deterministic event router — maps events to worker personas via plan rules."""

    def __init__(
        self,
        plans: list[PlanRoutingConfig] | None = None,
        *,
        policy_port: ProfilePolicyPort | None = None,
        plan_catalog: PlanCatalogPort | None = None,
    ) -> None:
        self._plans = plans or []
        self._policy_port = policy_port
        self._plan_catalog = plan_catalog

    def _plans_for_profile(self, profile_id: str) -> list[PlanRoutingConfig]:
        if self._plan_catalog is None:
            return self._plans
        catalog_plans = self._plan_catalog.load_active(profile_id)
        if not catalog_plans:
            return self._plans
        return [
            PlanRoutingConfig(
                id=entry.id,
                name=entry.name,
                description=entry.description,
                rules=[_rule_from_dict(raw) for raw in entry.rules],
            )
            for entry in catalog_plans
        ]

    @classmethod
    def from_plans_dir(
        cls,
        plans_dir: Path,
        *,
        policy_port: ProfilePolicyPort | None = None,
        plan_catalog: PlanCatalogPort | None = None,
    ) -> EventRouter:
        if get_use_dynamic_catalog() and plan_catalog is not None:
            catalog_plans = plan_catalog.load_active()
            if catalog_plans:
                configs = [
                    PlanRoutingConfig(
                        id=entry.id,
                        name=entry.name,
                        description=entry.description,
                        rules=[_rule_from_dict(raw) for raw in entry.rules],
                    )
                    for entry in catalog_plans
                ]
                return cls(configs, policy_port=policy_port, plan_catalog=plan_catalog)
        return cls(load_plans_from_dir(plans_dir), policy_port=policy_port, plan_catalog=plan_catalog)

    def route(self, event: SecurityEvent, *, profile_id: str = DEFAULT_PROFILE_ID) -> RoutingDecision:
        personas: list[str] = []
        playbook_id = ""
        notify_control = False
        matched_rules = 0
        matched_plan_id = ""
        matched_rule_idx = -1

        for plan in self._plans_for_profile(profile_id):
            for rule_idx, rule in enumerate(plan.rules):
                if not rule_matches(rule, event.type, event.severity):
                    continue
                matched_rules += 1
                matched_plan_id = plan.id
                matched_rule_idx = rule_idx
                for persona in rule.personas:
                    if persona not in personas:
                        personas.append(persona)
                if rule.playbook_id:
                    playbook_id = rule.playbook_id
                elif plan.id and not playbook_id:
                    playbook_id = plan.id
                notify_control = notify_control or rule.notify_control

        notify_severities = self._notify_control_severities(profile_id)
        if event.severity in notify_severities:
            notify_control = True

        if not personas:
            return RoutingDecision(
                event_id=event.id,
                jobs=[],
                reason="no_matching_rule",
                matched_plan_id=matched_plan_id,
                matched_rule_idx=matched_rule_idx,
            )

        return RoutingDecision(
            event_id=event.id,
            jobs=[f"{p}:{event.id}" for p in personas],
            playbook_id=playbook_id,
            personas=personas,
            notify_control=notify_control,
            reason=f"matched_{matched_rules}_rules",
            matched_plan_id=matched_plan_id,
            matched_rule_idx=matched_rule_idx,
        )

    def _notify_control_severities(self, profile_id: str) -> set[str]:
        if self._policy_port is None:
            raise RuntimeError("Profile policy port required for EventRouter")
        return self._policy_port.get_notify_control_severities(profile_id)


def _rule_from_dict(raw: dict):
    return parse_rule(raw)
