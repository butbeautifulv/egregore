from __future__ import annotations

from cys_core.application.policy_resolver import ProfilePolicyResolver


class _BoomLoader:
    def get_policy(self, _profile_id: str):
        raise RuntimeError("boom")


def test_policy_resolver_falls_back_on_loader_error() -> None:
    resolver = ProfilePolicyResolver(policy_loader=_BoomLoader())
    policy = resolver.policy("x")
    assert policy is not None

