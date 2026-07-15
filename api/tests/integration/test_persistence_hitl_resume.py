from __future__ import annotations

from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import MemorySaver

from cys_core.runtime.agent import AgentRuntime


@pytest.mark.integration
@pytest.mark.asyncio
async def test_runtime_uses_shared_checkpointer_for_resume(monkeypatch):
    import cys_core.runtime.agent as runtime_agent
    from cys_core.domain.agents.models import AgentDefinition

    checkpointer = MemorySaver()
    persistence = SimpleNamespace(checkpointer=checkpointer, store=None)

    defn = AgentDefinition(
        name="alpha",
        description="Alpha",
        role="worker",
        system_prompt="Prompt",
        schema_name=None,
        tools=[],
        hitl_tools={},
    )
    registry = SimpleNamespace(get=lambda _name: defn)
    model_connector = SimpleNamespace(create_model=lambda: "model", callbacks=lambda: [])

    runtime_a = AgentRuntime(
        registry,
        model_connector=model_connector,
        persistence_context=persistence,
        memory_reader=None,
    )
    runtime_b = AgentRuntime(
        registry,
        model_connector=model_connector,
        persistence_context=persistence,
        memory_reader=None,
    )

    captured: dict[str, object] = {}

    async def fake_ainvoke(*_args, **_kwargs):
        return {"messages": [SimpleNamespace(content='{"ok": true}')]}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(ainvoke=fake_ainvoke)

    monkeypatch.setattr(runtime_agent, "create_agent", fake_create_agent)

    await runtime_a.acreate(defn, session_id="worker:soc:job-1")
    assert captured.get("checkpointer") is checkpointer
    assert captured.get("store") is None
    assert "force_memory" not in str(captured)

    await runtime_b.aresume("alpha", "worker:soc:job-1", {"decision": "approve"})
