from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager

import httpx
import pytest
from langchain_core.messages import AIMessage, ChatMessage, HumanMessage, SystemMessage, ToolMessage


def _json_response(handler):
    @contextmanager
    def _fake_sync_http_client(*, timeout=None, headers=None, base_url=""):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            yield client

    @asynccontextmanager
    async def _fake_async_http_client(*, timeout=None, headers=None, base_url=""):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            yield client

    return _fake_sync_http_client, _fake_async_http_client


@pytest.mark.unit
def test_to_gateway_message_conversion():
    from cys_core.llm import model_gateway_provider as provider

    assert provider._to_gateway_message(HumanMessage(content="hi")) == {"role": "user", "content": "hi"}
    assert provider._to_gateway_message(ToolMessage(content="ok", tool_call_id="tool-1")) == {
        "role": "tool",
        "content": "ok",
        "tool_call_id": "tool-1",
    }
    ai_payload = provider._to_gateway_message(
        AIMessage(content="", tool_calls=[{"id": "tc-1", "name": "lookup", "args": {"q": "x"}}])
    )
    assert ai_payload["role"] == "assistant"
    assert ai_payload["tool_calls"][0]["function"]["name"] == "lookup"
    assert provider._to_gateway_message(ChatMessage(role="custom", content="fallback")) == {
        "role": "user",
        "content": "fallback",
    }


@pytest.mark.unit
def test_build_request_body_extracts_system_prompt_and_tools():
    from cys_core.llm import model_gateway_provider as provider

    model = provider.ModelGatewayChatModel(model="m", gateway_url="http://gw", persona="soc")
    bound = model.bind_tools([{"type": "function", "function": {"name": "dedup_alerts"}}])
    body = bound._build_request_body(
        [
            SystemMessage(content="agent"),
            SystemMessage(content="reminder"),
            HumanMessage(content="hi"),
        ]
    )
    assert body["persona"] == "soc"
    assert "agent" in body["system_prompt"]
    assert "reminder" in body["system_prompt"]
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["tools"][0]["function"]["name"] == "dedup_alerts"


@pytest.mark.unit
def test_generate_sync_posts_to_gateway(monkeypatch):
    from cys_core.llm import model_gateway_provider as provider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "content": "answer", "usage": {}})

    fake_sync, fake_async = _json_response(handler)
    monkeypatch.setattr(provider, "sync_http_client", fake_sync)
    monkeypatch.setattr(provider, "async_http_client", fake_async)

    model = provider.ModelGatewayChatModel(model="m", gateway_url="http://gw")
    result = model._generate([HumanMessage(content="hi")])
    assert result.generations[0].message.content == "answer"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agenerate_round_trips_tool_calls(monkeypatch):
    from cys_core.llm import model_gateway_provider as provider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "content": "",
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "dedup_alerts", "arguments": "{}"}}
                ],
            },
        )

    fake_sync, fake_async = _json_response(handler)
    monkeypatch.setattr(provider, "async_http_client", fake_async)

    model = provider.ModelGatewayChatModel(model="m", gateway_url="http://gw", shared_secret="s3cr3t")
    result = await model._agenerate([HumanMessage(content="dedup these")])
    message = result.generations[0].message
    assert isinstance(message, AIMessage)
    assert message.tool_calls[0]["name"] == "dedup_alerts"
    assert message.usage_metadata["total_tokens"] == 5


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agenerate_raises_on_upstream_failure(monkeypatch):
    from cys_core.llm import model_gateway_provider as provider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "error": "upstream provider unavailable"})

    fake_sync, fake_async = _json_response(handler)
    monkeypatch.setattr(provider, "async_http_client", fake_async)

    model = provider.ModelGatewayChatModel(model="m", gateway_url="http://gw")
    with pytest.raises(RuntimeError, match="upstream provider unavailable"):
        await model._agenerate([HumanMessage(content="hi")])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_astream_yields_single_chunk_fallback(monkeypatch):
    """model-gateway has no streaming endpoint — _astream must still satisfy the
    astream() contract callers (agent.astream) rely on, via one full-content chunk."""
    from cys_core.llm import model_gateway_provider as provider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "content": "full answer", "usage": {}})

    fake_sync, fake_async = _json_response(handler)
    monkeypatch.setattr(provider, "async_http_client", fake_async)

    model = provider.ModelGatewayChatModel(model="m", gateway_url="http://gw")
    chunks = [chunk async for chunk in model._astream([HumanMessage(content="hi")])]
    assert len(chunks) == 1
    assert chunks[0].message.content == "full answer"


@pytest.mark.unit
def test_provider_create_returns_configured_chat_model():
    from cys_core.llm import model_gateway_provider as provider

    created = provider.ModelGatewayProvider(gateway_url="http://gw:8093/", shared_secret="tok").create(
        model="m", api_key="", base_url=None, temperature=0.2, request_timeout=45.0
    )
    assert isinstance(created, provider.ModelGatewayChatModel)
    assert created.gateway_url == "http://gw:8093"
    assert created.shared_secret == "tok"
    assert created.temperature == 0.2
