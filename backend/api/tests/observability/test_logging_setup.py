"""Regression coverage for Discovery H.1 (docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md):
`configure_logging()` writing structlog JSON to stdout corrupted
SubprocessExecutionBackend/DockerExecutionBackend's stdout-as-IPC contract.
The bug was only caught by a live docker-compose + real-agent run because the
unit-test fake child never emits its own log lines — these tests make the
underlying invariant ("stream= routes away from stdout") checkable without
any live infrastructure, so a regression here fails fast in CI instead of
requiring another live-infra session to rediscover."""

from __future__ import annotations

import logging

import pytest

from cys_core.observability import logging_setup


@pytest.fixture(autouse=True)
def _reset_logging_state():
    logging_setup._configured = False
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    logging_setup._configured = False
    root.handlers.clear()
    root.handlers.extend(original_handlers)
    root.setLevel(original_level)


@pytest.mark.unit
def test_configure_logging_defaults_to_stdout(capsys):
    logging_setup.configure_logging("egregore-test")

    logging.getLogger("egregore.test").info("hello")

    captured = capsys.readouterr()
    assert "hello" in captured.out
    assert captured.err == ""


@pytest.mark.unit
def test_configure_logging_stream_stderr_keeps_stdout_clean(capsys):
    """This is the exact contract `cmd_run_sandboxed_job` relies on: its own
    log events must never appear on stdout, which SubprocessExecutionBackend
    parses as a single JSON RunResult document."""
    import sys

    logging_setup.configure_logging("egregore-worker-sandboxed", stream=sys.stderr)

    logging.getLogger("egregore.test").info("tool_call_started", extra={})

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "tool_call_started" in captured.err


@pytest.mark.unit
def test_configure_logging_is_idempotent_per_process():
    """Second call is a no-op (module-level `_configured` guard) — same as
    before this fix; `stream` on a later call must not silently override an
    already-configured handler."""
    import sys

    logging_setup.configure_logging("first")
    handler_after_first = logging.getLogger().handlers[0]

    logging_setup.configure_logging("second", stream=sys.stderr)

    assert logging.getLogger().handlers[0] is handler_after_first
