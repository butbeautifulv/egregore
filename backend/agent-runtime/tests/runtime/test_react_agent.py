from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from cys_core.domain.agents.models import AgentDefinition
from cys_core.runtime.react_agent import MinimalReactAgentRunner


class _FakeRegistry:
    def __init__(self, defn: AgentDefinition) -> None:
        self._defn = defn

    def get(self, name: str) -> AgentDefinition:
        return self._defn


class _FakeModel:
    def __init__(self, responses: list[AIMessage]) -> None:
        self._responses = list(responses)
        self.bound_tools: list[Any] | None = None
        self.calls: list[list[Any]] = []

    def bind_tools(self, tools: list[Any]) -> _FakeModel:
        self.bound_tools = tools
        return self

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        self.calls.append(list(messages))
        return self._responses.pop(0)


class _FakeModelConnector:
    def __init__(self, model: _FakeModel) -> None:
        self._model = model

    def create_model(self) -> _FakeModel:
        return self._model


class _FakeTool:
    def __init__(self, name: str, result: Any) -> None:
        self.name = name
        self._result = result
        self.invocations: list[dict[str, Any]] = []

    async def ainvoke(self, args: dict[str, Any]) -> Any:
        self.invocations.append(args)
        return self._result


def _defn(*, hitl_tools: dict[str, bool] | None = None) -> AgentDefinition:
    return AgentDefinition(
        name="soc",
        description="test persona",
        role="worker",
        system_prompt="You are a SOC analyst.",
        schema_name=None,
        hitl_tools=hitl_tools or {},
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_arun_returns_final_answer_with_no_tool_calls():
    model = _FakeModel([AIMessage(content="hello, no tools needed")])
    runner = MinimalReactAgentRunner(registry=_FakeRegistry(_defn()), model_connector=_FakeModelConnector(model))

    result = await runner.arun("soc", "hi", session_id="s1", sandbox_tools=[])

    assert result == {"raw_response": "hello, no tools needed"}
    assert len(model.calls) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_arun_executes_a_tool_call_and_feeds_result_back():
    tool = _FakeTool("list_incidents", {"incidents": []})
    tool_call_response = AIMessage(
        content="",
        tool_calls=[{"name": "list_incidents", "args": {}, "id": "call_1"}],
    )
    final_response = AIMessage(content='{"summary": "no open incidents"}')
    model = _FakeModel([tool_call_response, final_response])
    runner = MinimalReactAgentRunner(registry=_FakeRegistry(_defn()), model_connector=_FakeModelConnector(model))

    result = await runner.arun("soc", "any open incidents?", session_id="s2", sandbox_tools=[tool])

    assert tool.invocations == [{}]
    # No schema_name on this persona -> falls to the same no-schema wrap
    # AgentRuntime._coerce_result uses: {"response": json.dumps(data)}.
    assert result == {"response": json.dumps({"summary": "no open incidents"}, ensure_ascii=False)}
    assert len(model.calls) == 2
    assert model.bound_tools == [tool]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_arun_refuses_hitl_gated_tool_call_instead_of_executing_it():
    tool = _FakeTool("dangerous_action", "should never run")
    tool_call_response = AIMessage(
        content="",
        tool_calls=[{"name": "dangerous_action", "args": {}, "id": "call_1"}],
    )
    model = _FakeModel([tool_call_response])
    defn = _defn(hitl_tools={"dangerous_action": True})
    runner = MinimalReactAgentRunner(registry=_FakeRegistry(defn), model_connector=_FakeModelConnector(model))

    result = await runner.arun("soc", "do the dangerous thing", session_id="s3", sandbox_tools=[tool])

    assert "requires human approval" in result["error"]
    assert tool.invocations == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_arun_unknown_tool_name_becomes_tool_error_content_not_a_crash():
    tool_call_response = AIMessage(
        content="",
        tool_calls=[{"name": "does_not_exist", "args": {}, "id": "call_1"}],
    )
    final_response = AIMessage(content="")
    model = _FakeModel([tool_call_response, final_response])
    runner = MinimalReactAgentRunner(registry=_FakeRegistry(_defn()), model_connector=_FakeModelConnector(model))

    result = await runner.arun("soc", "call a bogus tool", session_id="s4", sandbox_tools=[])

    assert result == {"raw_response": ""}
    tool_message = model.calls[1][-1]
    assert "unknown tool" in tool_message.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_arun_hits_recursion_limit_if_model_never_stops_calling_tools():
    tool = _FakeTool("loop_tool", "ok")
    responses = [
        AIMessage(content="", tool_calls=[{"name": "loop_tool", "args": {}, "id": f"call_{i}"}]) for i in range(3)
    ]
    model = _FakeModel(responses)
    runner = MinimalReactAgentRunner(registry=_FakeRegistry(_defn()), model_connector=_FakeModelConnector(model))

    result = await runner.arun("soc", "loop forever", session_id="s5", sandbox_tools=[tool], recursion_limit=3)

    assert result == {"error": "recursion_limit_exceeded"}
    assert len(model.calls) == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_aresume_is_not_supported():
    runner = MinimalReactAgentRunner(
        registry=_FakeRegistry(_defn()), model_connector=_FakeModelConnector(_FakeModel([]))
    )

    result = await runner.aresume("soc", "s1", {"approved": True})

    assert "does not support HITL resume" in result["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_arun_is_registered_and_selectable_via_get_agent_runner():
    from cys_core.runtime.agent import get_agent_runner

    runner = get_agent_runner("react")

    assert isinstance(runner, MinimalReactAgentRunner)
