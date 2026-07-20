from __future__ import annotations

import pytest

from cys_core.runtime import agent as agent_module
from cys_core.runtime.agent import configure_agent_runner, get_agent_runner, get_runtime


@pytest.fixture(autouse=True)
def _restore_registry():
    """configure_agent_runner mutates module-level state — snapshot/restore around
    each test so registrations don't leak between tests."""
    original = dict(agent_module._AGENT_RUNNERS)
    yield
    agent_module._AGENT_RUNNERS.clear()
    agent_module._AGENT_RUNNERS.update(original)


@pytest.mark.unit
def test_default_agent_runner_is_langgraph_and_matches_get_runtime():
    assert get_agent_runner() is get_runtime()
    assert get_agent_runner("langgraph") is get_runtime()


@pytest.mark.unit
def test_unknown_agent_runner_name_raises():
    with pytest.raises(ValueError, match="Unknown agent runner"):
        get_agent_runner("some-other-product")


@pytest.mark.unit
def test_configure_agent_runner_registers_a_new_named_implementation():
    """Proves the actual swap mechanism end-to-end: registering a second
    AgentRunner-Protocol-shaped factory under a new name and selecting it by name
    is all a genuinely different agent implementation needs to do to plug in here —
    it does not need to touch ModelConnector, litellm, or LangChain at all
    (docs/MICROSERVICES_SPLIT_PLAN.md §1 item 4)."""

    class FakeAlternativeAgentRunner:
        async def arun(self, *args, **kwargs):
            return {"ok": True, "via": "fake-alternative"}

        async def aresume(self, *args, **kwargs):
            return {"resumed": True}

    fake_instance = FakeAlternativeAgentRunner()
    configure_agent_runner("fake-alternative", lambda: fake_instance)

    resolved = get_agent_runner("fake-alternative")

    assert resolved is fake_instance
    # The default entry is untouched by registering a new one.
    assert get_agent_runner() is get_runtime()


@pytest.mark.unit
def test_get_runtime_monkeypatch_still_reaches_default_registry_entry(monkeypatch):
    """Regression guard: the default registry entry is `lambda: get_runtime()`, not a
    directly-bound `get_runtime` reference — binding the function object directly
    would silently stop honoring `monkeypatch.setattr("cys_core.runtime.agent.get_runtime", ...)`,
    which several other tests (test_container_ingress.py) rely on."""
    sentinel = object()
    monkeypatch.setattr("cys_core.runtime.agent.get_runtime", lambda: sentinel)

    assert get_agent_runner("langgraph") is sentinel
