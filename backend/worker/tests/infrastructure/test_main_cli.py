from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _last_json_object(text: str) -> dict:
    return json.loads(text[text.find("{") :])


@pytest.mark.unit
def test_worker_cli_commands(monkeypatch, capsys):
    import interfaces.cli.main as main

    monkeypatch.setattr(main, "configure_logging", lambda _name: None)
    monkeypatch.setattr(main, "setup_otel", lambda **_kwargs: None)

    mock_orch = SimpleNamespace(
        process_next=AsyncMock(return_value=SimpleNamespace(model_dump=lambda: {"success": True}))
    )
    mock_container = SimpleNamespace(
        get_worker_orchestrator=lambda persona=None: mock_orch,
        get_trace_backend=lambda: SimpleNamespace(flush=lambda: None),
    )
    monkeypatch.setattr(main, "get_container", lambda: mock_container)

    assert main.cmd_worker(SimpleNamespace(once=True, max_jobs=1, daemon=False, persona="", idle_timeout=30.0)) == 0
    assert _last_json_object(capsys.readouterr().out)["result"]["success"] is True

    monkeypatch.setattr("interfaces.control_plane.status_store.get_status_store", lambda: SimpleNamespace(snapshot=lambda: {}))
    assert main.cmd_status(SimpleNamespace()) == 0
    capsys.readouterr()

    registry = SimpleNamespace(
        names=lambda: ["alpha"],
        by_workers=lambda: [SimpleNamespace(name="alpha")],
        get=lambda name: SimpleNamespace(name="alpha", role="worker", sample_input="sample"),
    )
    runtime = SimpleNamespace(run=lambda name, user_input, session_id: {"name": name, "input": user_input})
    monkeypatch.setattr(main, "get_agent_registry", lambda: registry)
    monkeypatch.setattr("cys_core.runtime.agent.get_runtime", lambda: runtime)
    assert main.cmd_agent(SimpleNamespace(name="alpha", input="explicit")) == 0
    capsys.readouterr()

    parser = main.build_parser()
    assert parser.parse_args(["worker", "--once"]).once is True
    assert parser.parse_args(["status"]).command == "status"
