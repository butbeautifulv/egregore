"""Prometheus multiprocess setup for API + worker daemon metric aggregation."""

from __future__ import annotations

import atexit
import os

_ENV = "PROMETHEUS_MULTIPROC_DIR"


def _mark_process_dead() -> None:
    if not os.environ.get(_ENV):
        return
    try:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(os.getpid())
    except Exception:
        return


if os.environ.get(_ENV):
    atexit.register(_mark_process_dead)
