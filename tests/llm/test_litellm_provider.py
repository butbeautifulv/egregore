from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from cys_core.llm.litellm_provider import LiteLLMChatModel, _chat_result_from_litellm
from cys_core.llm.tool_call_parsing import tool_calls_from_content


@tool
def investigate_incident(incident_id: str) -> str:
    """Fetch SIEM incident context."""
    return incident_id


def test_bind_tools_normalizes_any_tool_choice() -> None:
    model = LiteLLMChatModel(model="openai/test-model")
    bound = model.bind_tools([investigate_incident], tool_choice="any")
    assert bound.bound_tool_choice == "auto"

    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=[]))],
            usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )
        bound.invoke([HumanMessage(content="triage INC-1")], tool_choice="any")

    assert mock_completion.call_args.kwargs["tool_choice"] == "auto"


def test_bind_tools_passes_schemas_to_completion() -> None:
    model = LiteLLMChatModel(model="openai/test-model")
    bound = model.bind_tools([investigate_incident])
    assert bound.bound_tools is not None
    assert bound.bound_tools[0]["function"]["name"] == "investigate_incident"

    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="ok", tool_calls=[]),
                )
            ],
            usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )
        bound.invoke([HumanMessage(content="triage INC-1")])

    kwargs = mock_completion.call_args.kwargs
    assert "tools" in kwargs
    assert kwargs.get("tool_choice") in (None, "auto")
    assert kwargs["tools"][0]["function"]["name"] == "investigate_incident"


def test_chat_result_parses_native_tool_calls() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "investigate_incident",
                                "arguments": json.dumps({"incident_id": "inc-1"}),
                            },
                        }
                    ],
                )
            )
        ],
        usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    )
    result = _chat_result_from_litellm(response)
    message = result.generations[0].message
    assert isinstance(message, AIMessage)
    assert message.tool_calls[0]["name"] == "investigate_incident"
    assert message.tool_calls[0]["args"] == {"incident_id": "inc-1"}


def test_chat_result_parses_json_tool_calls_from_content() -> None:
    content = json.dumps(
        {
            "tool_calls": [
                {
                    "name": "list_incidents",
                    "arguments": {"limit": 3},
                }
            ]
        }
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))],
        usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    )
    result = _chat_result_from_litellm(response)
    message = result.generations[0].message
    assert message.tool_calls[0]["name"] == "list_incidents"
    assert message.tool_calls[0]["args"] == {"limit": 3}


def test_tool_calls_from_content_supports_legacy_fields() -> None:
    parsed = tool_calls_from_content(
        json.dumps({"tool_calls": [{"tool_name": "search_events", "tool_arguments": {"where": "x"}}]})
    )
    assert parsed[0]["name"] == "search_events"
    assert parsed[0]["args"] == {"where": "x"}


def test_round_trip_tool_message_serialization() -> None:
    from cys_core.llm.litellm_provider import _to_litellm_message

    ai = AIMessage(
        content="",
        tool_calls=[{"name": "investigate_incident", "args": {"incident_id": "x"}, "id": "1", "type": "tool_call"}],
    )
    payload = _to_litellm_message(ai)
    assert payload["tool_calls"][0]["function"]["name"] == "investigate_incident"
    assert json.loads(payload["tool_calls"][0]["function"]["arguments"]) == {"incident_id": "x"}

    tool_msg = _to_litellm_message(ToolMessage(content="done", tool_call_id="1"))
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "1"


async def test_astream_yields_content_chunks() -> None:
    model = LiteLLMChatModel(model="openai/test-model")

    async def mock_acompletion(**kwargs: object):
        assert kwargs.get("stream") is True

        async def gen():
            for text in ("hel", "lo"):
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=None))]
                )

        return gen()

    with patch("litellm.acompletion", side_effect=mock_acompletion):
        parts: list[str] = []
        async for chunk in model.astream([HumanMessage(content="hi")]):
            content = getattr(chunk, "content", None)
            if content is None and hasattr(chunk, "message"):
                content = chunk.message.content
            parts.append(content or "")
    assert "".join(parts) == "hello"


async def test_astream_falls_back_to_agenerate_on_error() -> None:
    model = LiteLLMChatModel(model="openai/test-model")
    with patch("litellm.acompletion", side_effect=RuntimeError("stream unavailable")):
        with patch.object(
            LiteLLMChatModel,
            "_agenerate",
            return_value=ChatResult(
                generations=[ChatGeneration(message=AIMessage(content="fallback"))],
            ),
        ):
            parts: list[str] = []
            async for chunk in model.astream([HumanMessage(content="hi")]):
                content = getattr(chunk, "content", None)
                if content is None and hasattr(chunk, "message"):
                    content = chunk.message.content
                parts.append(content or "")
    assert "".join(parts) == "fallback"
