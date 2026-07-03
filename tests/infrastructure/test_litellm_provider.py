from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ChatMessage, HumanMessage, SystemMessage, ToolMessage


@pytest.mark.unit
def test_llm_provider_selection_and_langfuse(monkeypatch):
    import cys_core.llm as llm

    class DummyProvider:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return {"created": kwargs}

    provider = DummyProvider()
    monkeypatch.setitem(llm._PROVIDERS, "dummy", provider)
    monkeypatch.setattr(llm.settings, "llm_provider", "dummy")
    monkeypatch.setattr(llm.settings, "llm_model", "model-a")
    monkeypatch.setattr(llm.settings, "openai_api_key", "api-key")
    monkeypatch.setattr(llm.settings, "llm_base_url", "https://llm.example")
    monkeypatch.setattr(llm.settings, "llm_temperature", 0.2)

    assert llm.get_provider("dummy") is provider
    monkeypatch.setitem(llm._MODEL_CONNECTORS, "dummy", llm.LLMConnector("dummy"))
    assert llm.get_model_connector("dummy").name == "dummy"
    assert llm.get_model()["created"]["model"] == "model-a"
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        llm.get_provider("missing")
    with pytest.raises(ValueError, match="Unknown model connector"):
        llm.get_model_connector("missing")

    monkeypatch.setattr(llm.settings, "langfuse_public_key", "")
    monkeypatch.setattr(llm.settings, "langfuse_secret_key", "")
    monkeypatch.setattr(llm.settings, "langfuse_api_key", "")
    assert llm.get_langfuse_callbacks() == []

    from cys_core.observability import langfuse_client

    langfuse_client.reset_langfuse_client_cache()

    class DummyCallbackHandler:
        pass

    class FakeTraceBackend:
        def get_callback_handler(self):
            if not llm.settings.langfuse_enabled:
                return None
            return DummyCallbackHandler()

    monkeypatch.setattr(
        "bootstrap.container.get_container",
        lambda: type("C", (), {"get_trace_backend": lambda self: FakeTraceBackend()})(),
    )
    monkeypatch.setattr(llm.settings, "langfuse_public_key", "public")
    monkeypatch.setattr(llm.settings, "langfuse_secret_key", "secret")
    callbacks = llm.get_langfuse_callbacks()
    assert len(callbacks) == 1
    assert isinstance(callbacks[0], DummyCallbackHandler)

    monkeypatch.setattr(
        "bootstrap.container.get_container",
        lambda: type("C", (), {"get_trace_backend": lambda self: type("T", (), {"get_callback_handler": lambda s: None})()})(),
    )
    assert llm.get_langfuse_callbacks() == []


@pytest.mark.unit
def test_normalize_messages_merges_system_at_start():
    from cys_core.llm import litellm_provider as provider

    messages = [
        SystemMessage(content="agent"),
        SystemMessage(content="sgr reminder"),
        HumanMessage(content="hi"),
    ]
    normalized = provider.normalize_messages_for_litellm(messages)
    assert len(normalized) == 2
    assert isinstance(normalized[0], SystemMessage)
    assert "agent" in str(normalized[0].content)
    assert "sgr reminder" in str(normalized[0].content)
    assert isinstance(normalized[1], HumanMessage)


@pytest.mark.unit
def test_litellm_message_conversion_and_sync_generation(monkeypatch):
    from cys_core.llm import litellm_provider as provider

    assert provider._to_litellm_message(SystemMessage(content="sys")) == {"role": "system", "content": "sys"}
    assert provider._to_litellm_message(HumanMessage(content="hi")) == {"role": "user", "content": "hi"}
    assert provider._to_litellm_message(ToolMessage(content="ok", tool_call_id="tool-1")) == {
        "role": "tool",
        "content": "ok",
        "tool_call_id": "tool-1",
    }
    ai_payload = provider._to_litellm_message(
        AIMessage(content="", tool_calls=[{"id": "tc-1", "name": "lookup", "args": {"q": "x"}}])
    )
    assert ai_payload["role"] == "assistant"
    assert ai_payload["tool_calls"][0]["function"]["name"] == "lookup"
    assert provider._to_litellm_message(ChatMessage(role="custom", content="fallback")) == {
        "role": "user",
        "content": "fallback",
    }

    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))])

    monkeypatch.setattr(provider.litellm, "completion", fake_completion)
    model = provider.LiteLLMChatModel(
        model="test-model",
        api_key="key",
        api_base="https://base.example",
        temperature=0.4,
        request_timeout=90.0,
    )
    assert model._llm_type == "litellm"
    assert model.bind_tools([]) is model
    result = model._generate([HumanMessage(content="hi")], stop=["END"], extra="value")

    assert result.generations[0].message.content == "answer"
    assert calls[0]["messages"][0]["role"] == "user"
    assert calls[0]["api_key"] == "key"
    assert calls[0]["api_base"] == "https://base.example"
    assert calls[0]["stop"] == ["END"]
    assert calls[0]["extra"] == "value"
    assert calls[0]["timeout"] == 90.0

    created = provider.LiteLLMProvider().create(
        model="m", api_key="", base_url=None, temperature=0.1, request_timeout=45.0
    )
    assert isinstance(created, provider.LiteLLMChatModel)
    assert created.api_key is None


@pytest.mark.unit
def test_litellm_generate_merges_multiple_system_messages(monkeypatch):
    from cys_core.llm import litellm_provider as provider

    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    monkeypatch.setattr(provider.litellm, "completion", fake_completion)
    model = provider.LiteLLMChatModel(model="test-model", temperature=0.1)
    model._generate(
        [
            SystemMessage(content="agent"),
            SystemMessage(content="reminder"),
            HumanMessage(content="hi"),
        ]
    )
    assert len(calls[0]["messages"]) == 2
    assert calls[0]["messages"][0]["role"] == "system"
    assert "agent" in calls[0]["messages"][0]["content"]
    assert "reminder" in calls[0]["messages"][0]["content"]
    assert calls[0]["messages"][1]["role"] == "user"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_litellm_async_generation(monkeypatch):
    from cys_core.llm import litellm_provider as provider

    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))])

    monkeypatch.setattr(provider.litellm, "acompletion", fake_acompletion)
    model = provider.LiteLLMChatModel(
        model="async-model",
        api_key="async-key",
        api_base="https://async.example",
        temperature=0.3,
        request_timeout=60.0,
    )
    result = await model._agenerate([HumanMessage(content="hi")], stop=["STOP"], flag=True)

    assert result.generations[0].message.content == ""
    assert calls[0]["model"] == "async-model"
    assert calls[0]["api_key"] == "async-key"
    assert calls[0]["api_base"] == "https://async.example"
    assert calls[0]["stop"] == ["STOP"]
    assert calls[0]["flag"] is True
    assert calls[0]["timeout"] == 60.0
