from __future__ import annotations

import json
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def _last_json_object(text: str) -> dict:
    return json.loads(text[text.find("{") :])


@pytest.mark.unit
def test_main_cli_commands_and_entrypoint(monkeypatch, capsys):
    import interfaces.cli.main as main

    monkeypatch.setattr(main, "configure_logging", lambda _name: None)
    monkeypatch.setattr(main, "setup_otel", lambda **_kwargs: None)

    ingest_result = (
        SimpleNamespace(id="e1", model_dump=lambda: {"id": "e1"}),
        SimpleNamespace(model_dump=lambda: {"personas": ["soc"]}),
        ["soc-e1-abc"],
    )
    monkeypatch.setattr(
        "interfaces.ingress.router.get_event_ingress",
        lambda: SimpleNamespace(ingest=lambda *a, **k: ingest_result),
    )
    mock_orch = SimpleNamespace(
        process_next=AsyncMock(return_value=SimpleNamespace(model_dump=lambda: {"success": True}))
    )
    mock_container = SimpleNamespace(
        get_worker_orchestrator=lambda persona=None: mock_orch,
        get_trace_backend=lambda: SimpleNamespace(flush=lambda: None),
    )
    monkeypatch.setattr(main, "get_container", lambda: mock_container)
    ingest_args = SimpleNamespace(
        type="siem.alert",
        payload='{"x":1}',
        severity="high",
        source="siem",
        event_id=None,
    )
    assert main.cmd_ingest(ingest_args) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["job_ids"] == ["soc-e1-abc"]

    assert main.cmd_worker(SimpleNamespace(once=True, max_jobs=1, daemon=False, persona="", idle_timeout=30.0)) == 0
    assert _last_json_object(capsys.readouterr().out)["result"]["success"] is True

    assert main.cmd_status(SimpleNamespace()) == 0
    capsys.readouterr()

    registry = SimpleNamespace(
        names=lambda: ["alpha"],
        by_workers=lambda: [SimpleNamespace(name="alpha")],
        get=lambda name: SimpleNamespace(name="alpha", role="worker", sample_input="sample"),
    )
    runtime = SimpleNamespace(run=lambda name, user_input, session_id: {"name": name, "input": user_input})
    monkeypatch.setattr("interfaces.cli.main.get_agent_registry", lambda: registry)
    monkeypatch.setattr("interfaces.cli.main.get_runtime", lambda: runtime)
    assert main.cmd_agent(SimpleNamespace(name="alpha", input="explicit")) == 0
    capsys.readouterr()

    pytest_main = MagicMock(return_value=5)
    monkeypatch.setattr(pytest, "main", pytest_main)
    assert main.cmd_adversarial_test(SimpleNamespace()) == 5

    info_registry = SimpleNamespace(
        names=lambda: ["alpha"],
        by_workers=lambda: [],
        by_control=lambda: [],
        get=lambda name: SimpleNamespace(role="worker"),
    )
    monkeypatch.setattr("interfaces.cli.main.get_agent_registry", lambda: info_registry)
    assert main.cmd_info(SimpleNamespace()) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "event-driven"

    monkeypatch.setattr("interfaces.ingress.router_consumer.run_router_consumer", lambda idle_timeout=0.0: 2)
    assert main.cmd_router(SimpleNamespace(idle_timeout=0.0)) == 0
    assert json.loads(capsys.readouterr().out)["processed"] == 2

    parser = main.build_parser()
    assert parser.parse_args(["ingest", "-t", "siem.alert", "-p", "{}"]).type == "siem.alert"
    assert parser.parse_args(["router"]).idle_timeout == 0.0


@pytest.mark.unit
def test_main_module_entrypoint_info(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["cys-agi", "info"])
    monkeypatch.setattr(
        "cys_core.registry.agents.get_agent_registry",
        lambda: SimpleNamespace(names=lambda: [], by_workers=lambda: [], by_control=lambda: []),
    )
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("interfaces.cli.main", run_name="__main__")
    assert exit_info.value.code == 0
