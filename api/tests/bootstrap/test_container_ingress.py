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
def test_docker_execution_backend_forwards_network_and_env_file(monkeypatch):
    """Live infra testing (docker/.secrets local stack) found DockerExecutionBackend
    wired with zero extra_run_args: `docker run` doesn't inherit the parent's env
    or join any particular network the way a plain subprocess does, so a job
    container spawned this way couldn't reach postgres/redis/the LLM provider.
    docker_network/docker_env_file settings close that gap."""
    monkeypatch.setenv("EXECUTION_BACKEND", "docker")
    monkeypatch.setenv("DOCKER_NETWORK", "deploy_default")
    monkeypatch.setenv("DOCKER_ENV_FILE", "deploy/.secrets/egregore-local.env")
    container = Container(Settings(use_kafka=False))
    captured: dict[str, object] = {}

    class FakeDockerBackend:
        def __init__(self, *, image, extra_run_args=None):
            captured["image"] = image
            captured["extra_run_args"] = extra_run_args

    monkeypatch.setattr(
        "cys_core.infrastructure.execution.docker_backend.DockerExecutionBackend",
        FakeDockerBackend,
    )

    container.get_worker_orchestrator(persona="soc")

    assert captured["extra_run_args"] == [
        "--network", "deploy_default",
        "--env-file", "deploy/.secrets/egregore-local.env",
    ]


@pytest.mark.unit
def test_docker_execution_backend_omits_args_when_unset(monkeypatch):
    monkeypatch.setenv("EXECUTION_BACKEND", "docker")
    container = Container(Settings(use_kafka=False))
    captured: dict[str, object] = {}

    class FakeDockerBackend:
        def __init__(self, *, image, extra_run_args=None):
            captured["extra_run_args"] = extra_run_args

    monkeypatch.setattr(
        "cys_core.infrastructure.execution.docker_backend.DockerExecutionBackend",
        FakeDockerBackend,
    )

    container.get_worker_orchestrator(persona="soc")

    assert captured["extra_run_args"] == []


@pytest.mark.unit
def test_meta_planner_uses_agent_runtime_not_ingress_orchestrator(monkeypatch):
    container = Container(Settings(use_kafka=False))
    runtime = MagicMock()
    monkeypatch.setattr(
        "cys_core.runtime.agent.get_runtime",
        lambda: runtime,
    )

    planner = container.get_meta_planner()

    assert planner._inner.runtime is runtime
