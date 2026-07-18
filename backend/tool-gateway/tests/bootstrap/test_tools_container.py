from __future__ import annotations

from types import SimpleNamespace

import pytest

from bootstrap.containers.tools_container import ToolsContainer, _resolve_scope_violation
from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.tools.exceptions import ScopeViolation
from cys_core.domain.tools.models import ToolInvokeCommand


def _command(**overrides) -> ToolInvokeCommand:
    base = {
        "tool_name": "run_active_scan",
        "args": {},
        "persona": "soc",
        "sandbox_id": "sb-1",
    }
    base.update(overrides)
    return ToolInvokeCommand(**base)


def _definition(name: str, tools: list[str]) -> AgentDefinition:
    return AgentDefinition(
        name=name,
        description="test",
        role="worker",
        system_prompt="test",
        tools=tools,
    )


def _container(mode: str) -> ToolsContainer:
    fake_outer = SimpleNamespace(settings=SimpleNamespace(tool_scope_mode=mode))
    return ToolsContainer(fake_outer)  # type: ignore[arg-type]


@pytest.mark.unit
def test_resolve_scope_violation_allows_tool_in_allowlist(monkeypatch):
    registry = type("Registry", (), {"get": lambda self, name: _definition(name, ["run_active_scan"])})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    assert _resolve_scope_violation(_command(tool_name="run_active_scan")) is None


@pytest.mark.unit
def test_resolve_scope_violation_flags_tool_outside_allowlist(monkeypatch):
    registry = type("Registry", (), {"get": lambda self, name: _definition(name, ["read_repo_metadata"])})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    assert _resolve_scope_violation(_command(tool_name="run_active_scan")) is not None


@pytest.mark.unit
def test_resolve_scope_violation_fails_open_for_unknown_persona(monkeypatch):
    def _raise_unknown(self, name):
        raise KeyError(f"Unknown agent: {name}")

    registry = type("Registry", (), {"get": _raise_unknown})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    # Must not raise, must not flag — an unregistered persona in this
    # package's catalog snapshot should not block every tool call for it.
    assert _resolve_scope_violation(_command(persona="unregistered-persona")) is None


@pytest.mark.unit
def test_check_scope_off_mode_never_checks(monkeypatch):
    registry = type("Registry", (), {"get": lambda self, name: _definition(name, [])})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    container = _container("off")
    container._check_scope(_command(tool_name="run_active_scan"))  # must not raise


@pytest.mark.unit
def test_check_scope_shadow_mode_logs_but_never_raises(monkeypatch):
    registry = type("Registry", (), {"get": lambda self, name: _definition(name, [])})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    container = _container("shadow")
    container._check_scope(_command(tool_name="run_active_scan"))  # must not raise


@pytest.mark.unit
def test_check_scope_enforce_mode_raises_on_violation(monkeypatch):
    registry = type("Registry", (), {"get": lambda self, name: _definition(name, [])})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    container = _container("enforce")
    with pytest.raises(ScopeViolation):
        container._check_scope(_command(tool_name="run_active_scan"))
