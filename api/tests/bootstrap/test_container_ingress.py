from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bootstrap.container import Container
from bootstrap.settings import Settings


@pytest.mark.unit
def test_container_ingress_factories_share_router():
    container = Container(Settings(use_kafka=False))
    router_a = container.get_event_router()
    router_b = container.get_event_router()
    ingress_a = container.get_event_ingress()
    ingress_b = container.get_event_ingress()
    dispatch_a = container.get_dispatch_event()
    dispatch_b = container.get_dispatch_event()

    assert router_a is router_b
    assert ingress_a is ingress_b
    assert dispatch_a is dispatch_b
    assert container.get_route_and_enqueue().router is router_a


@pytest.mark.unit
def test_container_worker_orchestrator_cached_by_persona(monkeypatch):
    container = Container(Settings(use_kafka=False))
    construct_count = 0

    class FakeOrchestrator:
        def __init__(self, persona: str | None = None) -> None:
            nonlocal construct_count
            construct_count += 1
            self.persona = persona

    monkeypatch.setattr(
        "interfaces.worker.orchestrator.WorkerOrchestrator",
        FakeOrchestrator,
    )

    default_a = container.get_worker_orchestrator()
    default_b = container.get_worker_orchestrator()
    soc_a = container.get_worker_orchestrator(persona="soc")
    soc_b = container.get_worker_orchestrator(persona="soc")

    assert default_a is default_b
    assert soc_a is soc_b
    assert default_a is not soc_a
    assert construct_count == 2


@pytest.mark.unit
def test_meta_planner_uses_agent_runtime_not_ingress_orchestrator(monkeypatch):
    container = Container(Settings(use_kafka=False))
    runtime = MagicMock()
    monkeypatch.setattr(container, "get_agent_runtime", lambda: runtime)

    planner = container.get_meta_planner()

    assert planner._inner.runtime is runtime
