from __future__ import annotations

import subprocess
import uuid
from typing import Any

from cys_core.infrastructure.config.infra_settings import get_docker_sandbox_settings

_MEMORY_LIMIT = "256m"
_CPU_LIMIT = "0.5"
_PIDS_LIMIT = "64"


def docker_available() -> bool:
    """Cheap host-side check — used to fail closed instead of falling back unsandboxed."""
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            timeout=get_docker_sandbox_settings().probe_timeout_s,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_python_in_docker(code: str, *, timeout: float, image: str) -> dict[str, Any]:
    """Execute Python code inside a locked-down, throwaway Docker container.

    No network, read-only rootfs (writable noexec tmpfs only), all Linux
    capabilities dropped, non-root user, bounded memory/CPU/pids. Fails closed
    (returns an error) if Docker itself is unavailable — callers must not fall
    back to unsandboxed execution on failure here.
    """
    if not code.strip():
        return {"success": False, "error": "empty code", "provider": "docker"}
    if not docker_available():
        return {
            "success": False,
            "error": "docker sandbox unavailable — refusing to run code unsandboxed",
            "provider": "docker",
        }

    container_name = f"egregore-pysandbox-{uuid.uuid4().hex[:12]}"
    cmd = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--name",
        container_name,
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        _PIDS_LIMIT,
        "--memory",
        _MEMORY_LIMIT,
        "--cpus",
        _CPU_LIMIT,
        "--user",
        "65534:65534",
        # Override the image entrypoint so we depend only on python3 being on PATH,
        # not on the image's default CMD/ENTRYPOINT. Code is fed on stdin (`-`).
        "--entrypoint",
        "python3",
        image,
        "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=code,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout[-8000:],
            "stderr": proc.stderr[-2000:],
            "exit_code": proc.returncode,
            "provider": "docker",
        }
    except subprocess.TimeoutExpired:
        # --rm normally cleans up when the docker CLI process is killed, but don't
        # rely on that — explicitly remove the container so a hung script can't
        # linger consuming resources.
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            timeout=get_docker_sandbox_settings().kill_timeout_s,
            check=False,
        )
        return {"success": False, "error": "sandbox timeout", "provider": "docker"}
    except FileNotFoundError:
        return {"success": False, "error": "docker CLI not found on host", "provider": "docker"}
