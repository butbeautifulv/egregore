from __future__ import annotations

import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest, multiprocess

_metrics_server: ThreadingHTTPServer | None = None
_metrics_thread: threading.Thread | None = None


def generate_metrics_payload() -> bytes:
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry)
    return generate_latest()


def render_metrics() -> Response:
    return Response(content=generate_metrics_payload(), media_type=CONTENT_TYPE_LATEST)


class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/health":
            body = b"ok\n"
            content_type = "text/plain; charset=utf-8"
        elif path == "/metrics":
            body = generate_metrics_payload()
            content_type = CONTENT_TYPE_LATEST
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def start_metrics_server(port: int, host: str = "0.0.0.0") -> None:
    global _metrics_server, _metrics_thread
    if _metrics_server is not None:
        return
    _metrics_server = ThreadingHTTPServer((host, port), _MetricsHandler)
    _metrics_thread = threading.Thread(
        target=_metrics_server.serve_forever,
        name="egregore-metrics-http",
        daemon=True,
    )
    _metrics_thread.start()


def stop_metrics_server() -> None:
    global _metrics_server, _metrics_thread
    if _metrics_server is None:
        return
    _metrics_server.shutdown()
    _metrics_server.server_close()
    _metrics_server = None
    _metrics_thread = None


def ensure_worker_metrics_server() -> int | None:
    """Start background /metrics when EGREGORE_METRICS_PORT is set (worker daemon)."""
    raw = os.environ.get("EGREGORE_METRICS_PORT", "").strip()
    if not raw:
        return None
    port = int(raw)
    from cys_core.observability.prometheus_setup import cleanup_multiproc_dir_on_startup

    cleanup_multiproc_dir_on_startup()
    start_metrics_server(port)
    return port


def mount_metrics(app: FastAPI) -> None:
    @app.get("/metrics")
    async def get_metrics() -> Response:
        return render_metrics()
