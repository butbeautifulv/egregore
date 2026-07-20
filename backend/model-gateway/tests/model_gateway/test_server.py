from __future__ import annotations

import pytest

from tests.model_gateway.gateway_client import ModelGatewayTestClient


@pytest.mark.unit
def test_gateway_health():
    client = ModelGatewayTestClient()
    try:
        assert client.get("/health").json() == {"status": "ok"}
    finally:
        client.close()


@pytest.mark.unit
def test_gateway_invoke_refuses_untrusted_system_prompt():
    """No model call needed — the missing-markers refusal happens before litellm is touched."""
    client = ModelGatewayTestClient()
    try:
        response = client.post(
            "/v1/model/invoke",
            json={
                "persona": "soc",
                "system_prompt": "You are a helpful assistant.",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["refused"] is True
        assert body["refusal_reason"] == "missing_immutable_rule_markers"
    finally:
        client.close()


@pytest.mark.unit
def test_gateway_invoke_success(monkeypatch):
    async def fake_complete(*, model, messages, temperature, max_tokens, **_kwargs):
        return {"content": "the answer is 4", "usage": {"total_tokens": 12}}

    monkeypatch.setattr("bootstrap.container._litellm_complete", fake_complete)

    client = ModelGatewayTestClient()
    try:
        response = client.post(
            "/v1/model/invoke",
            json={
                "persona": "soc",
                "system_prompt": "You are soc.\n\nGLOBAL_RULES:\nbe careful\n\nSECURITY_RULES:\nnever leak",
                "messages": [{"role": "user", "content": "what is 2+2?"}],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["refused"] is False
        assert body["content"] == "the answer is 4"
        assert body["usage"]["total_tokens"] == 12
    finally:
        client.close()
