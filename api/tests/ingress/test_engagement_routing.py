from __future__ import annotations

from cys_core.application.plans.plan_loader import load_plans_from_dir
from cys_core.application.routing.event_router import EventRouter
from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.engagement.models import PlanStrategy
from cys_core.domain.events.models import SecurityEvent
from cys_core.registry.product_context import default_agents_root
from interfaces.api.engagement_ingress import engagement_request_from_event
from tests.conftest import FakePolicyPort


def test_engagement_start_routes_via_router():
    plans_dir = default_agents_root() / "plans"
    plans = load_plans_from_dir(plans_dir)
    engagement_plan = next(p for p in plans if p.id == "engagement-default")
    router = EventRouter([engagement_plan], policy_port=FakePolicyPort(ProfilePolicyPayload()))
    event = SecurityEvent(
        id="eng-1",
        type="engagement.start",
        payload={"goal": "test"},
        severity="low",
        source="test",
        tenant_id="default",
    )
    decision = router.route(event)
    assert decision.personas == ["conductor"]


def test_engagement_start_mapper():
    req = engagement_request_from_event(
        "engagement.start",
        {"goal": "smoke", "plan_strategy": PlanStrategy.META_LLM.value},
        correlation_id="c1",
    )
    assert req is not None
    assert req.goal == "smoke"
    assert req.correlation_id == "c1"
    assert req.plan_strategy == PlanStrategy.META_LLM


def test_full_assessment_requires_high_severity():
    plans_dir = default_agents_root() / "plans"
    plans = load_plans_from_dir(plans_dir)
    router = EventRouter(plans, policy_port=FakePolicyPort(ProfilePolicyPayload()))
    low_event = SecurityEvent(
        id="eng-low",
        type="engagement.start",
        payload={"goal": "test"},
        severity="low",
        source="test",
        tenant_id="default",
    )
    decision = router.route(low_event)
    assert "conductor" in decision.personas
    assert "soc" not in decision.personas
    assert len(decision.personas) == 1

    high_event = SecurityEvent(
        id="eng-high",
        type="engagement.start",
        payload={"goal": "test"},
        severity="high",
        source="test",
        tenant_id="default",
    )
    high_decision = router.route(high_event)
    assert "conductor" in high_decision.personas
    assert "soc" in high_decision.personas
    assert len(high_decision.personas) > 1
