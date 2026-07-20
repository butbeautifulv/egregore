from __future__ import annotations

import pytest

from cys_core.application.ports.lazy_agent_runner import LazyInProcessAgentRunner


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lazy_runner_defers_arun_to_get_runtime(monkeypatch):
    calls: list[tuple[str, tuple, dict]] = []

    class FakeRuntime:
        async def arun(self, *args, **kwargs):
            calls.append(("arun", args, kwargs))
            return {"ok": True}

        async def aresume(self, *args, **kwargs):
            calls.append(("aresume", args, kwargs))
            return {"resumed": True}

    fake_runtime = FakeRuntime()
    monkeypatch.setattr("cys_core.runtime.agent.get_runtime", lambda: fake_runtime)

    runner = LazyInProcessAgentRunner()
    result = await runner.arun("soc", "investigate", session_id="s1")

    assert result == {"ok": True}
    assert calls == [("arun", ("soc", "investigate"), {"session_id": "s1"})]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lazy_runner_defers_aresume_to_get_runtime(monkeypatch):
    class FakeRuntime:
        async def arun(self, *args, **kwargs):
            raise AssertionError("arun should not be called")

        async def aresume(self, *args, **kwargs):
            return {"resumed": True, "args": args, "kwargs": kwargs}

    monkeypatch.setattr("cys_core.runtime.agent.get_runtime", lambda: FakeRuntime())

    runner = LazyInProcessAgentRunner()
    result = await runner.aresume("soc", "session-1", {"decision": "approve"})

    assert result["resumed"] is True
    assert result["args"] == ("soc", "session-1", {"decision": "approve"})


@pytest.mark.unit
def test_lazy_runner_does_not_import_agent_module_until_called():
    """Constructing the proxy must not touch cys_core.runtime.agent at all —
    that's the entire point (deferring the langchain/langgraph import cost
    until a non-in_process backend actually needs in-process execution,
    which today it never does)."""
    import sys

    had_module_before = "cys_core.runtime.agent" in sys.modules
    LazyInProcessAgentRunner()
    # Construction alone must not newly import the module — if it wasn't
    # already loaded by some other test in this process, it still isn't.
    if not had_module_before:
        assert "cys_core.runtime.agent" not in sys.modules
