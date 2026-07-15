from __future__ import annotations

import time
from http.client import HTTPConnection

import pytest

from cys_core.observability import http as metrics_http
from cys_core.observability.prometheus_setup import cleanup_multiproc_dir_on_startup


@pytest.fixture(autouse=True)
def _reset_metrics_server():
    metrics_http.stop_metrics_server()
    yield
    metrics_http.stop_metrics_server()


def test_metrics_handler_health_and_metrics():
    metrics_http.start_metrics_server(0, host="127.0.0.1")
    assert metrics_http._metrics_server is not None
    port = metrics_http._metrics_server.server_address[1]

    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/health")
    health = conn.getresponse()
    assert health.status == 200
    assert health.read() == b"ok\n"
    conn.close()

    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/metrics")
    resp = conn.getresponse()
    assert resp.status == 200
    body = resp.read()
    assert b"python_info" in body or body.startswith(b"#")
    conn.close()


def test_multiprocess_collector_when_mproc_dir_set(tmp_path):
    import subprocess
    import sys

    mpdir = tmp_path / "prom-multiproc"
    mpdir.mkdir()
    script = f"""
import os
os.environ["PROMETHEUS_MULTIPROC_DIR"] = {str(mpdir)!r}
from cys_core.observability.metrics import metrics
from cys_core.observability import http as metrics_http
with metrics.track_worker_job("consultant"):
    pass
payload = metrics_http.generate_metrics_payload()
assert b"cys_worker_job_duration_seconds" in payload
"""
    subprocess.run([sys.executable, "-c", script], check=True, cwd=str(tmp_path))


def test_cleanup_multiproc_dir_removes_dead_pid_files(tmp_path, monkeypatch):
    mpdir = tmp_path / "prom-multiproc"
    mpdir.mkdir()
    dead = mpdir / "counter_999999.db"
    dead.write_text("stale", encoding="utf-8")
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(mpdir))

    cleanup_multiproc_dir_on_startup()
    assert not dead.exists()


def test_ensure_worker_metrics_server_starts_from_env(monkeypatch):
    monkeypatch.setenv("EGREGORE_METRICS_PORT", "0")
    port = metrics_http.ensure_worker_metrics_server()
    assert port == 0
    assert metrics_http._metrics_server is not None
    time.sleep(0.05)
    assert metrics_http._metrics_thread is not None
    assert metrics_http._metrics_thread.is_alive()
