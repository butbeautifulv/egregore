from __future__ import annotations

from typing import Any

import pytest

from cys_core.application.ports.profile_policy import ProfilePolicyPort
from cys_core.domain.catalog.models import (
    AgentCatalogEntry,
    ProfilePack,
    ProfilePolicyPayload,
)
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog
from cys_core.infrastructure.catalog.profile_policy import ProfilePolicyLoader


class FakePolicyPort(ProfilePolicyPort):
    """Shared fake for ProfilePolicyPort contract tests."""

    def __init__(self, policy: ProfilePolicyPayload) -> None:
        self._policy = policy

    def get_policy(self, profile_id: str) -> ProfilePolicyPayload:
        return self._policy

    def get_trust_floor(self, profile_id: str) -> float:
        return self._policy.trust_floor

    def get_bus_policy(self, profile_id: str) -> dict[str, list[str]]:
        return self._policy.bus_policy

    def get_escalation_paths(self, profile_id: str) -> set[tuple[str, str]]:
        return set()

    def get_hitl_threshold(self, profile_id: str) -> str:
        return self._policy.hitl_auto_approve_threshold

    def get_max_spawn_depth(self, profile_id: str) -> int:
        return self._policy.max_spawn_depth

    def get_cost_per_1k_tokens(self, profile_id: str) -> float:
        return self._policy.cost_per_1k_tokens_usd

    def get_notify_control_severities(self, profile_id: str) -> set[str]:
        return set(self._policy.notify_control_severities)

    def get_default_personas(self, profile_id: str) -> list[str] | None:
        return None


def catalog_with_soc_profile(
    *,
    policy: ProfilePolicyPayload | None = None,
    default_personas: list[str] | None = None,
    agents: list[AgentCatalogEntry] | None = None,
) -> InMemoryAgentCatalog:
    catalog = InMemoryAgentCatalog()
    personas = ["consultant", "soc"] if default_personas is None else default_personas
    pack = ProfilePack(
        id=DEFAULT_PROFILE_ID,
        name="SOC",
        policy=policy or ProfilePolicyPayload(),
        default_personas=personas,
    )
    seed_agents = agents or [
        AgentCatalogEntry(name="soc", role="worker", enabled=True, profile_id=DEFAULT_PROFILE_ID),
        AgentCatalogEntry(name="consultant", role="worker", enabled=True, profile_id=DEFAULT_PROFILE_ID),
        AgentCatalogEntry(
            name="conductor",
            role="coordinator",
            enabled=True,
            profile_id=DEFAULT_PROFILE_ID,
            capabilities=["research", "spawn_worker"],
        ),
    ]
    catalog.seed(seed_agents, pack)
    return catalog


def patch_catalog(monkeypatch, catalog: InMemoryAgentCatalog) -> None:
    """Patch common catalog singleton targets to use an in-memory catalog."""
    monkeypatch.setattr(
        "cys_core.infrastructure.catalog.catalog_registry.get_agent_catalog",
        lambda: catalog,
    )
    monkeypatch.setattr(
        "bootstrap.container.get_agent_catalog",
        lambda: catalog,
    )
    monkeypatch.setattr(
        "bootstrap.container.Container.get_agent_catalog",
        lambda self: catalog,
    )
    loader = ProfilePolicyLoader(lambda: catalog)
    monkeypatch.setattr(
        "cys_core.infrastructure.catalog.profile_policy._loader",
        lambda: loader,
    )
    from cys_core.application.policy_resolver import ProfilePolicyResolver, set_policy_resolver

    set_policy_resolver(ProfilePolicyResolver(policy_loader=loader))


def default_policy_port() -> FakePolicyPort:
    return FakePolicyPort(ProfilePolicyPayload())


def make_event_router(plans):
    from cys_core.application.routing.event_router import EventRouter

    return EventRouter(plans, policy_port=default_policy_port())


class FakeRunRuntime:
    """Minimal async runtime stub for application use-case tests."""

    def __init__(self, *, responses: list[dict[str, Any]] | None = None) -> None:
        self._responses = list(responses or [{"reply": "ok"}])
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def arun(self, name: str, user_input: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((name, user_input, kwargs))
        if self._responses:
            return self._responses.pop(0)
        return {"reply": "ok"}


@pytest.fixture
def fake_runtime() -> FakeRunRuntime:
    return FakeRunRuntime()


@pytest.fixture
def soc_catalog() -> InMemoryAgentCatalog:
    return catalog_with_soc_profile()


@pytest.fixture(autouse=True)
def _reset_container_and_memory_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use in-memory catalog and reset DI container between tests."""
    import bootstrap.container as container_mod
    from bootstrap.settings import get_settings

    monkeypatch.setenv("AUTH_ENABLED", "0")
    monkeypatch.setenv("USE_MEMORY_FALLBACK", "true")
    get_settings.cache_clear()
    container_mod._container = None
    from cys_core.infrastructure.catalog.catalog_singletons import CatalogSingletons

    CatalogSingletons.reset()
    catalog = catalog_with_soc_profile()
    patch_catalog(monkeypatch, catalog)
    monkeypatch.setattr(
        "cys_core.infrastructure.catalog.registry_factory._use_postgres",
        lambda: False,
    )
    yield
    container_mod._container = None
    CatalogSingletons.reset()


@pytest.fixture
def reset_infra_caches() -> None:
    """Reset singleton infrastructure connectors between tests."""
    from cys_core.infrastructure.bus_transport import reset_bus_transport_cache
    from cys_core.infrastructure.kafka_publisher import reset_kafka_publisher_cache
    from cys_core.infrastructure.queue import reset_job_queue_cache

    reset_job_queue_cache()
    reset_kafka_publisher_cache()
    reset_bus_transport_cache()
    yield
    reset_job_queue_cache()
    reset_kafka_publisher_cache()
    reset_bus_transport_cache()


@pytest.fixture
async def fastapi_app(monkeypatch: pytest.MonkeyPatch):
    """FastAPI app with lifespan for API integration tests."""
    from unittest.mock import AsyncMock, MagicMock

    from httpx import ASGITransport, AsyncClient

    from interfaces.api.app import create_app

    ingress = MagicMock()
    ingress.aingest = AsyncMock(return_value=([], MagicMock(), []))
    app = create_app(ingress=ingress)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", lifespan="on") as client:
        yield client, app


@pytest.fixture
async def kafka_queue(reset_infra_caches, monkeypatch: pytest.MonkeyPatch):
    """Isolated KafkaJobQueue with broker calls patched out."""
    from unittest.mock import AsyncMock, MagicMock

    from cys_core.infrastructure.kafka_queue import KafkaJobQueue

    queue = KafkaJobQueue(persona="consultant", bootstrap_servers="localhost:19092")
    monkeypatch.setattr(queue, "_ensure_producer", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(queue, "_ensure_consumer", AsyncMock(return_value=True))
    yield queue
    if hasattr(queue, "aclose"):
        await queue.aclose()
