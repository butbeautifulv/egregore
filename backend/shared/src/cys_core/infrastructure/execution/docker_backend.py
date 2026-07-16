from __future__ import annotations

from cys_core.domain.workers.models import RunResult, WorkerJob
from cys_core.infrastructure.execution.subprocess_backend import SubprocessExecutionBackend


class DockerExecutionBackend:
    """Local analog of K8sExecutionBackend via `docker run`, for dev/CI without
    a real cluster (Phase 3.3, docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md).

    Unlike K8s (where the pod's stdout isn't something the Dispatcher can read
    as simply as a subprocess's), a non-detached `docker run -i ...` forwards
    the container's stdin/stdout to the docker CLI process exactly like a
    plain subprocess does — so this reuses SubprocessExecutionBackend's stdin-
    envelope-in/stdout-RunResult-out plumbing wholesale via composition instead
    of the job_store-polling path K8sExecutionBackend needs. No
    K8S_SANDBOX_CREDENTIALS_ONLY-style env var is needed either: that flag
    exists only because K8sSandboxConnector.create() would otherwise spawn a
    second Kubernetes Job (Discovery F) — the Docker sandbox connector path
    has no equivalent placement side effect to double up on.
    """

    owns_timeout = True

    def __init__(
        self,
        *,
        image: str,
        docker_executable: str = "docker",
        extra_run_args: list[str] | None = None,
    ) -> None:
        argv = [
            docker_executable,
            "run",
            "--rm",
            "-i",
            *(extra_run_args or []),
            image,
            "uv",
            "run",
            "egregore",
            "run-sandboxed-job",
            "--job-json",
            "-",
        ]
        self._delegate = SubprocessExecutionBackend(command=argv)

    async def execute(
        self,
        job: WorkerJob,
        budgeted: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
    ) -> RunResult:
        return await self._delegate.execute(job, budgeted, session_id, job_state)
