from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from cys_core.domain.catalog.models import (
    AgentCatalogEntry,
    CatalogVersion,
    PersonaQuality,
    ProfilePack,
    ProfilePolicyPayload,
    QualitySignals,
)


@dataclass
class FakeCorrelationIdPort:
    def bind(self, correlation_id: str) -> object:
        return object()

    def reset(self, token: object) -> None:
        return None


@dataclass
class FakeWorkerTracingPort:
    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[None]:
        yield None


@dataclass
class FakeResourceSource:
    personas: list[str] = field(default_factory=lambda: ["soc", "network", "consultant"])

    def list_worker_personas(self, profile_id: str | None = None) -> list[str]:
        return list(self.personas)


@dataclass
class FakePersonaRanking:
    def rank(self, personas: list[str], *, profile_id: str = "cybersec-soc") -> list[str]:
        return list(personas)


@dataclass
class FakeAgentCatalog:
    enabled: set[str] = field(default_factory=lambda: {"soc", "network", "consultant"})

    def get_agent(self, name: str) -> AgentCatalogEntry | None:
        if name not in self.enabled:
            return None
        return AgentCatalogEntry(
            name=name,
            enabled=True,
            quality=PersonaQuality(empirical_trust=0.8),
        )

    def list_agents(self, *, profile_id: str | None = None, enabled_only: bool = True) -> list[AgentCatalogEntry]:
        return []

    def upsert_agent(self, entry: AgentCatalogEntry) -> AgentCatalogEntry:
        return entry

    def delete_agent(self, name: str, *, profile_id: str = "cybersec-soc") -> bool:
        return False

    def list_profiles(self) -> list[ProfilePack]:
        return []

    def upsert_profile(self, profile: ProfilePack) -> ProfilePack:
        return profile

    def get_version(self, profile_id: str) -> CatalogVersion:
        return CatalogVersion(profile_id=profile_id, version=1)

    def seed(self, entries: list[AgentCatalogEntry], profile: ProfilePack, **kwargs: Any) -> None:
        return None


@dataclass
class FakeSchemaRegistry:
    def get(self, name: str | None) -> object:
        return object()


@dataclass
class FakePolicyPort:
    trust_floor: float = 0.5
    ema_alpha: float = 0.3

    def get_trust_floor(self, profile_id: str) -> float:
        return self.trust_floor

    def get_bus_policy(self, profile_id: str) -> dict[str, list[str]]:
        return {}

    def get_escalation_paths(self, profile_id: str) -> set[tuple[str, str]]:
        return set()

    def get_hitl_threshold(self, profile_id: str) -> str:
        return "low"

    def get_max_spawn_depth(self, profile_id: str) -> int:
        return 2

    def get_cost_per_1k_tokens(self, profile_id: str) -> float:
        return 0.003

    def get_policy(self, profile_id: str) -> ProfilePolicyPayload:
        return ProfilePolicyPayload(
            quality_signals=QualitySignals(
                job_success=0.8,
                job_failure=0.2,
                trace_critic_pass=0.7,
                trace_critic_fail=0.3,
                hitl_pause=0.5,
                bus_failure=0.4,
                ema_alpha=self.ema_alpha,
            )
        )

    def get_notify_control_severities(self, profile_id: str) -> set[str]:
        return {"critical", "high"}


def fake_correlation_id_port() -> FakeCorrelationIdPort:
    return FakeCorrelationIdPort()


def fake_catalog_seed_loaders(*, skills=None, plans=None, mcp_servers=None):
    from types import SimpleNamespace

    return SimpleNamespace(
        load_skills=lambda profile_id: list(skills or []),
        load_plans=lambda profile_id: list(plans or []),
        load_mcp_servers=lambda profile_id: list(mcp_servers or []),
    )


def fake_worker_tracing_port() -> FakeWorkerTracingPort:
    return FakeWorkerTracingPort()


def fake_resource_source(personas: list[str] | None = None) -> FakeResourceSource:
    return FakeResourceSource(personas=personas or ["soc", "network", "consultant"])


def fake_persona_ranking() -> FakePersonaRanking:
    return FakePersonaRanking()


def fake_agent_catalog(enabled: list[str] | None = None) -> FakeAgentCatalog:
    return FakeAgentCatalog(enabled=set(enabled or ["soc", "network", "consultant"]))


def fake_schema_registry() -> FakeSchemaRegistry:
    return FakeSchemaRegistry()


def fake_policy_port(*, trust_floor: float = 0.5, ema_alpha: float = 0.3) -> FakePolicyPort:
    return FakePolicyPort(trust_floor=trust_floor, ema_alpha=ema_alpha)


def run_step_port_kwargs():
    from types import SimpleNamespace

    # Lazy: analyze_task_hints is part of the confirmed-dead run_step/manage_run
    # cluster (plan §1) and lives in worker only — this function is only ever
    # called from worker's own test_run_step*/test_manage_run.py.
    from cys_core.application.use_cases.analyze_task_hints import AnalyzeTaskHints

    return {
        "context_summarizer": SimpleNamespace(summarize=lambda **kwargs: "summary"),
        "reflexion_store": SimpleNamespace(
            append=lambda *args, **kwargs: None,
            list_for_investigation=lambda *args, **kwargs: [],
        ),
        "policy_port": fake_policy_port(),
        "task_hints": AnalyzeTaskHints(),
    }


def run_worker_job_port_kwargs():
    return {
        "schema_registry": fake_schema_registry(),
        "agent_catalog": fake_agent_catalog(),
    }


def plan_investigation_port_kwargs(**overrides):
    base = {
        "resource_source": fake_resource_source(),
        "persona_ranking": fake_persona_ranking(),
        "agent_catalog": fake_agent_catalog(),
    }
    base.update(overrides)
    return base
