from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bootstrap.container import Container
from bootstrap.settings import Settings


@pytest.mark.unit
def test_container_worker_orchestrator_cached_by_persona(monkeypatch):
    container = Container(Settings(use_kafka=False))
    construct_count = 0

    class FakeOrchestrator:
        def __init__(self, persona: str | None = None, runtime=None, **_kwargs) -> None:
            nonlocal construct_count
            construct_count += 1
            self.persona = persona

    monkeypatch.setattr(
        "interfaces.worker.orchestrator.WorkerOrchestrator",
        FakeOrchestrator,
    )
    monkeypatch.setattr("cys_core.runtime.agent.get_runtime", lambda: None)

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


@pytest.mark.unit
def test_subprocess_backend_worker_orchestrator_gets_lazy_runtime_not_real_agent_runtime(monkeypatch):
    """Regression: get_worker_orchestrator() used to call cys_core.runtime.agent.get_runtime()
    unconditionally, before branching on execution_backend — meaning subprocess/k8s/docker modes
    (whose actual job execution never touches `runtime` at all, see WorkerOrchestrator.run_job)
    still forced an eager import of the langchain/langgraph-dependent agent runtime just to pick
    an out-of-process backend. Fixed by passing LazyInProcessAgentRunner instead of a real one for
    non-in_process backends (docs/MICROSERVICES_SPLIT_PLAN.md §1 item 2)."""
    from bootstrap.lazy_agent_runner import LazyInProcessAgentRunner

    monkeypatch.setenv("EXECUTION_BACKEND", "subprocess")
    container = Container(Settings(use_kafka=False))
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        def __init__(self, *, persona=None, runtime=None, execution_backend=None, **_kwargs):
            captured["runtime"] = runtime

    monkeypatch.setattr("interfaces.worker.orchestrator.WorkerOrchestrator", FakeOrchestrator)

    def _fail_get_runtime():
        raise AssertionError("get_runtime() must not be called for backend_kind='subprocess'")

    monkeypatch.setattr("cys_core.runtime.agent.get_runtime", _fail_get_runtime)

    container.get_worker_orchestrator(persona="soc")

    assert isinstance(captured["runtime"], LazyInProcessAgentRunner)


@pytest.mark.unit
def test_k8s_backend_worker_orchestrator_gets_lazy_runtime_not_real_agent_runtime(monkeypatch):
    from bootstrap.lazy_agent_runner import LazyInProcessAgentRunner

    monkeypatch.setenv("EXECUTION_BACKEND", "k8s")
    container = Container(Settings(use_kafka=False))
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        def __init__(self, *, persona=None, runtime=None, execution_backend=None, **_kwargs):
            captured["runtime"] = runtime

    monkeypatch.setattr("interfaces.worker.orchestrator.WorkerOrchestrator", FakeOrchestrator)

    def _fail_get_runtime():
        raise AssertionError("get_runtime() must not be called for backend_kind='k8s'")

    monkeypatch.setattr("cys_core.runtime.agent.get_runtime", _fail_get_runtime)

    container.get_worker_orchestrator(persona="soc")

    assert isinstance(captured["runtime"], LazyInProcessAgentRunner)


@pytest.mark.unit
def test_docker_backend_worker_orchestrator_gets_lazy_runtime_not_real_agent_runtime(monkeypatch):
    from bootstrap.lazy_agent_runner import LazyInProcessAgentRunner

    monkeypatch.setenv("EXECUTION_BACKEND", "docker")
    container = Container(Settings(use_kafka=False))
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        def __init__(self, *, persona=None, runtime=None, execution_backend=None, **_kwargs):
            captured["runtime"] = runtime

    monkeypatch.setattr("interfaces.worker.orchestrator.WorkerOrchestrator", FakeOrchestrator)

    def _fail_get_runtime():
        raise AssertionError("get_runtime() must not be called for backend_kind='docker'")

    monkeypatch.setattr("cys_core.runtime.agent.get_runtime", _fail_get_runtime)

    container.get_worker_orchestrator(persona="soc")

    assert isinstance(captured["runtime"], LazyInProcessAgentRunner)


@pytest.mark.unit
def test_meta_planner_gets_lazy_runtime_for_subprocess_backend(monkeypatch):
    from bootstrap.lazy_agent_runner import LazyInProcessAgentRunner

    monkeypatch.setenv("EXECUTION_BACKEND", "subprocess")
    container = Container(Settings(use_kafka=False))

    def _fail_get_runtime():
        raise AssertionError("get_runtime() must not be called for backend_kind='subprocess'")

    monkeypatch.setattr("cys_core.runtime.agent.get_runtime", _fail_get_runtime)

    planner = container.get_meta_planner()

    assert isinstance(planner._inner.runtime, LazyInProcessAgentRunner)
