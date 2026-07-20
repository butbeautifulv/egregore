from __future__ import annotations

import pytest

from bootstrap.container import Container
from bootstrap.settings import Settings

# Note: no in_process-mode tests here (and no tests exercising
# cys_core.runtime.agent.get_runtime/configure_agent_runner at all) — dispatcher no longer
# carries cys_core/runtime or cys_core/middleware (docs/MICROSERVICES_SPLIT_PLAN.md §1);
# in_process is a structurally invalid EXECUTION_BACKEND for this package now. That coverage
# stays in backend/worker and backend/agent-runtime, which still have the module.


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
def test_subprocess_backend_worker_orchestrator_gets_lazy_runtime(monkeypatch):
    """LazyInProcessAgentRunner is what backs `runtime=` for subprocess/k8s/docker
    execution backends — its arun/aresume would raise ModuleNotFoundError if ever
    actually called here (cys_core.runtime.agent doesn't exist in this package), but
    nothing calls them: actual job execution is fully delegated to the child process
    (docs/MICROSERVICES_SPLIT_PLAN.md §1)."""
    from bootstrap.lazy_agent_runner import LazyInProcessAgentRunner

    monkeypatch.setenv("EXECUTION_BACKEND", "subprocess")
    container = Container(Settings(use_kafka=False))
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        def __init__(self, *, persona=None, runtime=None, execution_backend=None, **_kwargs):
            captured["runtime"] = runtime

    monkeypatch.setattr("interfaces.worker.orchestrator.WorkerOrchestrator", FakeOrchestrator)

    container.get_worker_orchestrator(persona="soc")

    assert isinstance(captured["runtime"], LazyInProcessAgentRunner)


@pytest.mark.unit
def test_k8s_backend_worker_orchestrator_gets_lazy_runtime(monkeypatch):
    from bootstrap.lazy_agent_runner import LazyInProcessAgentRunner

    monkeypatch.setenv("EXECUTION_BACKEND", "k8s")
    container = Container(Settings(use_kafka=False))
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        def __init__(self, *, persona=None, runtime=None, execution_backend=None, **_kwargs):
            captured["runtime"] = runtime

    monkeypatch.setattr("interfaces.worker.orchestrator.WorkerOrchestrator", FakeOrchestrator)

    container.get_worker_orchestrator(persona="soc")

    assert isinstance(captured["runtime"], LazyInProcessAgentRunner)


@pytest.mark.unit
def test_docker_backend_worker_orchestrator_gets_lazy_runtime(monkeypatch):
    from bootstrap.lazy_agent_runner import LazyInProcessAgentRunner

    monkeypatch.setenv("EXECUTION_BACKEND", "docker")
    container = Container(Settings(use_kafka=False))
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        def __init__(self, *, persona=None, runtime=None, execution_backend=None, **_kwargs):
            captured["runtime"] = runtime

    monkeypatch.setattr("interfaces.worker.orchestrator.WorkerOrchestrator", FakeOrchestrator)

    container.get_worker_orchestrator(persona="soc")

    assert isinstance(captured["runtime"], LazyInProcessAgentRunner)


@pytest.mark.unit
def test_meta_planner_gets_lazy_runtime_for_subprocess_backend(monkeypatch):
    from bootstrap.lazy_agent_runner import LazyInProcessAgentRunner

    monkeypatch.setenv("EXECUTION_BACKEND", "subprocess")
    container = Container(Settings(use_kafka=False))

    planner = container.get_meta_planner()

    assert isinstance(planner._inner.runtime, LazyInProcessAgentRunner)


@pytest.mark.unit
def test_in_process_backend_fails_clearly_not_silently(monkeypatch):
    """in_process is structurally unsupported now — cys_core/runtime and
    cys_core/middleware live in backend/agent-runtime, not here. Confirm the failure
    is an immediate, clear error at the composition-root call site, not a silent
    no-op or a deep ModuleNotFoundError traceback."""
    monkeypatch.setenv("EXECUTION_BACKEND", "in_process")
    container = Container(Settings(use_kafka=False))

    with pytest.raises(NotImplementedError, match="not supported in backend/dispatcher"):
        container.get_worker_orchestrator(persona="soc")


@pytest.mark.unit
def test_subprocess_backend_forwards_agent_runtime_python_executable(monkeypatch):
    """AGENT_RUNTIME_PYTHON_EXECUTABLE is how dispatcher points its subprocess spawns at
    backend/agent-runtime's own venv instead of its own sys.executable (docs/
    MICROSERVICES_SPLIT_PLAN.md §1 item 2)."""
    monkeypatch.setenv("EXECUTION_BACKEND", "subprocess")
    monkeypatch.setenv("AGENT_RUNTIME_PYTHON_EXECUTABLE", "/opt/agent-runtime/.venv/bin/python")
    container = Container(Settings(use_kafka=False))
    captured: dict[str, object] = {}

    class FakeSubprocessBackend:
        def __init__(self, *, python_executable=None, command=None):
            captured["python_executable"] = python_executable

    monkeypatch.setattr(
        "cys_core.infrastructure.execution.subprocess_backend.SubprocessExecutionBackend",
        FakeSubprocessBackend,
    )

    container.get_worker_orchestrator(persona="soc")

    assert captured["python_executable"] == "/opt/agent-runtime/.venv/bin/python"


@pytest.mark.unit
def test_subprocess_backend_fails_clearly_when_python_executable_unset(monkeypatch):
    """Silently falling back to sys.executable would spawn a child that crashes
    mid-job (cys_core.runtime doesn't exist in dispatcher's venv) instead of
    failing clearly at orchestrator construction — same discipline as
    test_in_process_backend_fails_clearly_not_silently above."""
    monkeypatch.setenv("EXECUTION_BACKEND", "subprocess")
    monkeypatch.delenv("AGENT_RUNTIME_PYTHON_EXECUTABLE", raising=False)
    container = Container(Settings(use_kafka=False))

    with pytest.raises(NotImplementedError, match="AGENT_RUNTIME_PYTHON_EXECUTABLE"):
        container.get_worker_orchestrator(persona="soc")


@pytest.mark.unit
def test_meta_planner_always_gets_lazy_runtime_regardless_of_backend(monkeypatch):
    from bootstrap.lazy_agent_runner import LazyInProcessAgentRunner

    monkeypatch.setenv("EXECUTION_BACKEND", "k8s")
    container = Container(Settings(use_kafka=False))

    planner = container.get_meta_planner()

    assert isinstance(planner._inner.runtime, LazyInProcessAgentRunner)
