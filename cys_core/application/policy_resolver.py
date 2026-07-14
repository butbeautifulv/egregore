from __future__ import annotations

from typing import Any

from cys_core.application.ports.metrics import MetricsPort
from cys_core.domain.catalog.models import ProfilePolicyPayload

_resolver: ProfilePolicyResolver | None = None


class ProfilePolicyResolver:
    """Single read-path: catalog policy → env shim → domain defaults."""

    def __init__(
        self,
        *,
        policy_loader=None,
        env_overrides: dict[str, Any] | None = None,
        metrics_port: MetricsPort | None = None,
    ) -> None:
        self._loader = policy_loader
        self._env = env_overrides or {}
        self._metrics = metrics_port

    def policy(self, profile_id: str) -> ProfilePolicyPayload:
        if self._loader is not None:
            try:
                loaded = self._loader.get_policy(profile_id)
                if loaded is not None:
                    return loaded
            except Exception:
                # FIXME: swallows the loader exception itself (only records a metric) — persistence/config
                # errors here are indistinguishable from "no override configured" and fall through silently.
                if self._metrics is not None:
                    try:
                        self._metrics.record_persistence_fallback("policy_loader")
                    except Exception:
                        pass
        from cys_core.domain.policy.product_payloads import profile_policy_for

        return profile_policy_for(profile_id)

    def trace_critic_threshold(self, profile_id: str) -> float:
        env = self._env.get("trace_critic_threshold")
        if env is not None:
            return float(env)
        return self.policy(profile_id).trace_critic.threshold

    def trace_critic_every_n(self, profile_id: str) -> int:
        env = self._env.get("trace_critic_every_n_steps")
        if env is not None:
            return int(env)
        return self.policy(profile_id).trace_critic.every_n_steps

    def trace_critic_rerun_max(self, profile_id: str) -> int:
        env = self._env.get("trace_critic_rerun_max")
        if env is not None:
            return int(env)
        return self.policy(profile_id).trace_critic.rerun_max

    def delegate_budget_fraction(self, profile_id: str) -> float:
        env = self._env.get("delegate_budget_fraction")
        if env is not None:
            return float(env)
        return self.policy(profile_id).delegate_budget_fraction

    def max_spawn_depth(self, profile_id: str) -> int:
        env = self._env.get("max_spawn_depth")
        if env is not None:
            return int(env)
        if self._loader is not None:
            try:
                return self._loader.get_max_spawn_depth(profile_id)
            except Exception:
                # FIXME: no logging — a loader failure silently falls back to the policy default instead
                # of surfacing that spawn-depth override lookup is broken.
                pass
        return self.policy(profile_id).max_spawn_depth

    def planner_fallback_personas(
        self,
        profile_id: str,
        *,
        env_csv: str = "",
        max_personas: int = 3,
    ) -> list[str]:
        if env_csv.strip():
            return [p.strip() for p in env_csv.split(",") if p.strip()][:max_personas]
        if self._loader is not None:
            try:
                personas = self._loader.get_default_personas(profile_id)
                if personas and len(personas) <= max_personas:
                    return personas
            except Exception:
                # FIXME: no logging — loader failure silently falls back to ["consultant"] instead of
                # surfacing that default-personas lookup is broken.
                pass
        return ["consultant"]

    def sgr_policy(self, profile_id: str):
        from cys_core.domain.reasoning.sgr_models import SgrPolicy

        return self.policy(profile_id).sgr or SgrPolicy()


def env_overrides_from_settings(settings: Any) -> dict[str, Any]:
    return {
        "trace_critic_threshold": settings.trace_critic_threshold,
        "trace_critic_every_n_steps": settings.trace_critic_every_n_steps,
        "trace_critic_rerun_max": settings.trace_critic_rerun_max,
        "delegate_budget_fraction": settings.delegate_budget_fraction,
        "max_spawn_depth": settings.max_spawn_depth,
    }


def set_policy_resolver(resolver: ProfilePolicyResolver) -> None:
    global _resolver
    _resolver = resolver


def get_profile_policy_resolver() -> ProfilePolicyResolver:
    if _resolver is not None:
        return _resolver
    return ProfilePolicyResolver()


def configure_policy_resolver_from_settings(
    settings: Any, *, policy_loader=None, metrics_port: MetricsPort | None = None
) -> ProfilePolicyResolver:
    """Build resolver from settings env shim + optional catalog loader; register as global."""
    resolver = ProfilePolicyResolver(
        policy_loader=policy_loader,
        env_overrides=env_overrides_from_settings(settings),
        metrics_port=metrics_port,
    )
    set_policy_resolver(resolver)
    return resolver
