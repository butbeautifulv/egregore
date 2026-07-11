"""Prometheus multiprocess setup for API + worker daemon metric aggregation."""

from __future__ import annotations

from typing import Any

import atexit
import os
import re

_ENV = "PROMETHEUS_MULTIPROC_DIR"
_MPROC_FILE = re.compile(r"^(counter|gauge|histogram|summary)_(\d+)\.db$")


def _mark_process_dead() -> None:
    if not os.environ.get(_ENV):
        return
    try:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(os.getpid())
    except Exception:
        return


def cleanup_multiproc_dir_on_startup() -> None:
    """Drop stale multiproc metric files from dead PIDs in this pod."""
    mpdir = os.environ.get(_ENV)
    if not mpdir or not os.path.isdir(mpdir):
        return
    current = os.getpid()
    multiprocess: Any = None
    try:
        from prometheus_client import multiprocess as _multiprocess

        multiprocess = _multiprocess
    except Exception:
        pass

    for name in os.listdir(mpdir):
        match = _MPROC_FILE.match(name)
        if not match:
            continue
        pid = int(match.group(2))
        if pid == current:
            continue
        alive = True
        try:
            os.kill(pid, 0)
        except OSError:
            alive = False
        if alive:
            continue
        path = os.path.join(mpdir, name)
        try:
            os.remove(path)
        except OSError:
            pass
        if multiprocess is not None:
            try:
                multiprocess.mark_process_dead(pid)
            except Exception:
                pass


if os.environ.get(_ENV):
    atexit.register(_mark_process_dead)
