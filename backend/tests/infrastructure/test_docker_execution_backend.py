from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.execution.docker_backend import DockerExecutionBackend

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "docker_backend_test_image"
_IMAGE = "egregore-docker-backend-test:latest"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=5, check=True)
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(not _docker_available(), reason="Docker not available")


@pytest.fixture(scope="module", autouse=True)
def _built_test_image():
    subprocess.run(
        ["docker", "build", "-t", _IMAGE, str(_FIXTURE_DIR)],
        check=True,
        capture_output=True,
    )
    yield


def _job(job_id: str = "j1") -> WorkerJob:
    return WorkerJob(job_id=job_id, event_id="e1", persona="soc", payload={"alert": "x"})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_docker_execution_backend_real_round_trip():
    """Real `docker run` integration test (not mocked) — proves the
    docker-run/stdin/stdout plumbing DockerExecutionBackend hardcodes
    (`docker run --rm -i <image> uv run egregore run-sandboxed-job
    --job-json -`) actually works, using a minimal stand-in image with a fake
    `uv` shim instead of the full egregore project image."""
    backend = DockerExecutionBackend(image=_IMAGE)
    job = _job()

    result = await backend.execute(job, job, "session-1", {})

    assert result.success is True
    assert result.job_id == job.job_id
    assert result.persona == job.persona
    assert backend.owns_timeout is True
