from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel


class DemoSchema(BaseModel):
    value: str


class StrictSchema(BaseModel):
    value: int


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_create_run_invoke_and_deep_agent_tool(monkeypatch):
    import cys_core.runtime.agent as runtime_agent
    from cys_core.domain.agents.models import AgentDefinition

    defn = AgentDefinition(
        name="alpha",
        description="Alpha",
        role="specialist",
        system_prompt="Prompt",
        schema_name=None,
        tools=["enrich_ioc"],
        hitl_tools={"run_active_scan": True, "read_repo_metadata": False},
    )
    registry = SimpleNamespace(get=lambda name: defn, names=lambda: ["alpha"])
    model_connector = SimpleNamespace(create_model=lambda: "model", callbacks=lambda: [])
    async def async_persistence():
        return SimpleNamespace(checkpointer="async-cp", store="async-store")

    runtime = runtime_agent.AgentRuntime(
        registry,
        model_connector=model_connector,
        sync_persistence_provider=lambda: SimpleNamespace(checkpointer="cp", store="store"),
        async_persistence_provider=async_persistence,
        memory_reader=None,
    )

    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(created=True)

    monkeypatch.setattr(runtime_agent, "create_agent", fake_create_agent)
    created = runtime.create(defn, session_id="sid", extra_tools=["extra-tool"])
    assert created.created is True
    assert captured["name"] == "alpha"
    assert captured["model"] == "model"
    assert captured["checkpointer"] == "cp"
    assert captured["store"] == "store"
    assert captured["tools"][-1] == "extra-tool"
    assert len(captured["middleware"]) >= 4

    async_created = await runtime.acreate(defn, session_id="async-sid", extra_tools=["async-extra"])
    assert async_created.created is True
    assert captured["checkpointer"] == "async-cp"
    assert captured["tools"][-1] == "async-extra"

    monkeypatch.setattr(runtime, "create", lambda loaded_defn, session_id, **_kwargs: SimpleNamespace(agent=True))
    monkeypatch.setattr(
        runtime,
        "_invoke",
        lambda agent, text, session_id, schema, **_kwargs: {"sid": session_id, "text": text},
    )
    assert runtime.run("alpha", "input", session_id="custom") == {"sid": "custom", "text": "input"}
    assert runtime.run("alpha", "input")["sid"] == "agent-alpha"

    async def fake_runtime_ainvoke(agent, text, session_id, schema, recursion_limit=None, **_kwargs):
        return {"sid": session_id, "text": text}

    monkeypatch.setattr(runtime, "_ainvoke", fake_runtime_ainvoke)
    assert await runtime.arun("alpha", "input", session_id="async-custom") == {
        "sid": "async-custom",
        "text": "input",
    }

    invoker = runtime_agent.AgentRuntime(SimpleNamespace(), model_connector=model_connector)
    structured_result = SimpleNamespace(
        invoke=lambda *_args, **_kwargs: {"structured_response": DemoSchema(value="ok")}
    )
    assert invoker._invoke(structured_result, "text", session_id="sid", schema=DemoSchema) == {"value": "ok"}

    dict_result = SimpleNamespace(invoke=lambda *_args, **_kwargs: {"structured_response": {"value": "dict"}})
    assert invoker._invoke(dict_result, "text", session_id="sid", schema=None) == {"value": "dict"}

    no_messages = SimpleNamespace(invoke=lambda *_args, **_kwargs: {"messages": []})
    assert invoker._invoke(no_messages, "text", session_id="sid", schema=None) == {"error": "no response"}

    list_content = [SimpleNamespace(content=[{"text": '{"value": "from-list"}'}])]
    list_result = SimpleNamespace(invoke=lambda *_args, **_kwargs: {"messages": list_content})
    assert invoker._invoke(list_result, "text", session_id="sid", schema=DemoSchema) == {"value": "from-list"}

    raw_result = SimpleNamespace(invoke=lambda *_args, **_kwargs: {"messages": [SimpleNamespace(content="not-json")]})
    assert invoker._invoke(raw_result, "text", session_id="sid", schema=None) == {"raw_response": "not-json"}

    invalid_schema = SimpleNamespace(
        invoke=lambda *_args, **_kwargs: {"messages": [SimpleNamespace(content='{"bad": "data"}')]}
    )
    monkeypatch.setattr(runtime_agent, "get_stage", lambda: "dev")
    assert invoker._invoke(invalid_schema, "text", session_id="sid", schema=StrictSchema) == {"bad": "data"}
    monkeypatch.setattr(runtime_agent, "get_stage", lambda: "test")
    with pytest.raises(runtime_agent.SecurityViolation):
        invoker._invoke(invalid_schema, "text", session_id="sid", schema=StrictSchema)

    valid_json = SimpleNamespace(
        invoke=lambda *_args, **_kwargs: {"messages": [SimpleNamespace(content='{"ok": true}')]}
    )
    assert invoker._invoke(valid_json, "text", session_id="sid", schema=None)["response"] == '{"ok": true}'

    async def fake_agent_ainvoke(*_args, **_kwargs):
        return {"structured_response": DemoSchema(value="async")}

    async_agent = SimpleNamespace(ainvoke=fake_agent_ainvoke)
    assert await invoker._ainvoke(async_agent, "text", session_id="sid", schema=DemoSchema) == {"value": "async"}

    subagent = invoker.to_deep_agent_subagent(defn)
    assert subagent["name"] == "alpha"
    assert subagent["tools"][0].name == "enrich_ioc"

    runtime_agent.get_runtime.cache_clear()
    try:
        assert isinstance(runtime_agent.get_runtime(), runtime_agent.AgentRuntime)
    finally:
        runtime_agent.get_runtime.cache_clear()
