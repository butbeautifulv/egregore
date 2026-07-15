from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from cys_core.infrastructure.tools.adapters import docker_sandbox


@pytest.mark.unit
def test_run_python_rejects_empty_code():
    result = docker_sandbox.run_python_in_docker("   ", timeout=5, image="python:3.12-slim")
    assert result["success"] is False
    assert result["error"] == "empty code"


@pytest.mark.unit
def test_run_python_fails_closed_when_docker_unavailable(monkeypatch):
    # The whole point of this sandbox is that arbitrary model code must NEVER run
    # with the worker's own privileges. If Docker isn't there, we must refuse —
    # not silently execute on the host.
    monkeypatch.setattr(docker_sandbox, "docker_available", lambda: False)
    called = False

    def _boom(*args, **kwargs):  # pragma: no cover - must not be reached
        nonlocal called
        called = True
        raise AssertionError("subprocess.run must not be called when docker is unavailable")

    monkeypatch.setattr(docker_sandbox.subprocess, "run", _boom)

    result = docker_sandbox.run_python_in_docker("print(1)", timeout=5, image="python:3.12-slim")

    assert called is False
    assert result["success"] is False
    assert "unsandboxed" in result["error"]


@pytest.mark.unit
def test_run_python_uses_hardened_docker_flags(monkeypatch):
    monkeypatch.setattr(docker_sandbox, "docker_available", lambda: True)
    captured: dict[str, object] = {}

    def _fake_run(cmd, *, input, capture_output, text, timeout, check):
        captured["cmd"] = cmd
        captured["input"] = input
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(docker_sandbox.subprocess, "run", _fake_run)

    result = docker_sandbox.run_python_in_docker("print('ok')", timeout=7, image="python:3.12-slim")

    assert result["success"] is True
    assert result["stdout"] == "ok"
    cmd = captured["cmd"]
    # Every hardening flag that makes this a real security boundary must be present.
    assert "--network" in cmd and cmd[cmd.index("--network") + 1] == "none"
    assert "--read-only" in cmd
    assert "--cap-drop" in cmd and cmd[cmd.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges" in cmd
    assert "--user" in cmd and cmd[cmd.index("--user") + 1] == "65534:65534"
    assert "--entrypoint" in cmd and cmd[cmd.index("--entrypoint") + 1] == "python3"
    assert cmd[-2:] == ["python:3.12-slim", "-"]
    assert captured["input"] == "print('ok')"


@pytest.mark.unit
def test_run_python_timeout_force_removes_container(monkeypatch):
    monkeypatch.setattr(docker_sandbox, "docker_available", lambda: True)
    removed: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        if cmd[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))
        removed.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(docker_sandbox.subprocess, "run", _fake_run)

    result = docker_sandbox.run_python_in_docker("while True: pass", timeout=1, image="python:3.12-slim")

    assert result["success"] is False
    assert result["error"] == "sandbox timeout"
    # A hung container must be force-removed, not left lingering.
    assert removed and removed[0][:3] == ["docker", "rm", "-f"]
