from __future__ import annotations

import pytest

from cys_core.application.policy_resolver import ProfilePolicyResolver, get_profile_policy_resolver, set_policy_resolver
from cys_core.domain.catalog.models import ModePolicyPayload, ProfilePolicyPayload, TraceCriticPolicy
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.runs.mode_policy import ModePolicy
from cys_core.domain.runs.models import InteractionMode
from cys_core.infrastructure.catalog.profile_policy import ProfilePolicyLoader
from tests.conftest import FakePolicyPort, catalog_with_soc_profile


@pytest.mark.unit
def test_resolver_precedence_env_over_catalog():
    catalog = catalog_with_soc_profile(
        policy=ProfilePolicyPayload(
            trace_critic=TraceCriticPolicy(threshold=0.7, every_n_steps=5, rerun_max=3),
            delegate_budget_fraction=0.2,
            max_spawn_depth=4,
        ),
        default_personas=["soc"],
    )
    loader = ProfilePolicyLoader(lambda: catalog)
    resolver = ProfilePolicyResolver(
        policy_loader=loader,
        env_overrides={
            "trace_critic_threshold": 0.9,
            "trace_critic_every_n_steps": 2,
            "trace_critic_rerun_max": 1,
            "delegate_budget_fraction": 0.5,
            "max_spawn_depth": 2,
        },
    )
    assert resolver.trace_critic_threshold(DEFAULT_PROFILE_ID) == 0.9
    assert resolver.trace_critic_every_n(DEFAULT_PROFILE_ID) == 2
    assert resolver.trace_critic_rerun_max(DEFAULT_PROFILE_ID) == 1
    assert resolver.delegate_budget_fraction(DEFAULT_PROFILE_ID) == 0.5
    assert resolver.max_spawn_depth(DEFAULT_PROFILE_ID) == 2


@pytest.mark.unit
def test_resolver_precedence_catalog_over_defaults():
    catalog = catalog_with_soc_profile(
        policy=ProfilePolicyPayload(
            trace_critic=TraceCriticPolicy(threshold=0.65),
            max_spawn_depth=3,
        ),
    )
    loader = ProfilePolicyLoader(lambda: catalog)
    resolver = ProfilePolicyResolver(policy_loader=loader)
    assert resolver.trace_critic_threshold(DEFAULT_PROFILE_ID) == 0.65
    assert resolver.max_spawn_depth(DEFAULT_PROFILE_ID) == 3


@pytest.mark.unit
def test_resolver_planner_fallback_catalog_then_env():
    catalog = catalog_with_soc_profile(default_personas=["network", "soc"])
    loader = ProfilePolicyLoader(lambda: catalog)
    resolver = ProfilePolicyResolver(policy_loader=loader)
    assert resolver.planner_fallback_personas(DEFAULT_PROFILE_ID) == ["network", "soc"]

    empty = ProfilePolicyResolver(
        policy_loader=ProfilePolicyLoader(lambda: catalog_with_soc_profile(default_personas=[]))
    )
    assert empty.planner_fallback_personas(DEFAULT_PROFILE_ID, env_csv="intel,hunter") == ["intel", "hunter"]

    bare = ProfilePolicyResolver()
    assert bare.planner_fallback_personas(DEFAULT_PROFILE_ID, env_csv="") == ["consultant"]


@pytest.mark.unit
def test_mode_policy_with_injected_profile_payload():
    port = FakePolicyPort(
        ProfilePolicyPayload(
            mode_policy=ModePolicyPayload(
                read_only_tools=["web_search"],
                plan_blocked_tools=["spawn_worker"],
                mutating_tools=["spawn_worker"],
            )
        )
    )
    mode_policy = port.get_policy(DEFAULT_PROFILE_ID).mode_policy
    assert ModePolicy.allow_tool(InteractionMode.ASK, "web_search", mode_policy=mode_policy) is True
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "spawn_worker", mode_policy=mode_policy) is False


@pytest.mark.unit
def test_resolver_global_registration():
    catalog = catalog_with_soc_profile(
        policy=ProfilePolicyPayload(max_spawn_depth=7),
    )
    loader = ProfilePolicyLoader(lambda: catalog)
    resolver = ProfilePolicyResolver(policy_loader=loader)
    set_policy_resolver(resolver)
    assert get_profile_policy_resolver().max_spawn_depth(DEFAULT_PROFILE_ID) == 7
