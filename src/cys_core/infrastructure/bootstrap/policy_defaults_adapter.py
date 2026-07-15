from __future__ import annotations

from bootstrap import policy_defaults as _policy_defaults
from cys_core.application.ports.policy_defaults import PolicyDefaultsPort


class BootstrapPolicyDefaultsAdapter:
    def default_profile_policy(self):
        return _policy_defaults.default_profile_policy()


def build_policy_defaults_port() -> PolicyDefaultsPort:
    return BootstrapPolicyDefaultsAdapter()
