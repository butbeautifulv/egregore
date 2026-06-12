from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cys_core.domain.rag.models import ChunkACL, DocumentProvenance, RagChunk
from interfaces.gateways.tool.adapters.rag import rag_query_tool
from interfaces.gateways.tool.server import create_app
from interfaces.rag.store import MemoryVectorStore


def _seed(store: MemoryVectorStore) -> None:
    store.upsert(
        [
            RagChunk(
                chunk_id="c1",
                text="Runbook: triage encoded powershell alerts",
                acl=ChunkACL(tenant="default", roles=["analyst"]),
                provenance=DocumentProvenance(source_id="kb", content_hash="h1"),
            )
        ]
    )


@pytest.mark.unit
def test_rag_query_tool_success(monkeypatch):
    store = MemoryVectorStore()
    _seed(store)
    monkeypatch.setattr("interfaces.rag.retrieve.get_vector_store", lambda: store)
    data = rag_query_tool(query="powershell triage", persona="soc", tenant="default")
    assert data["success"] is True
    assert "BEGIN_RETRIEVED_CONTENT" in data["content"]


@pytest.mark.unit
def test_gateway_invoke_rag_query(monkeypatch):
    store = MemoryVectorStore()
    _seed(store)
    monkeypatch.setattr("interfaces.rag.retrieve.get_vector_store", lambda: store)

    client = TestClient(create_app())
    response = client.post(
        "/invoke",
        json={
            "tool_name": "rag_query",
            "args": {"query": "powershell", "persona": "soc", "tenant": "default"},
            "persona": "soc",
            "sandbox_id": "sandbox-1",
        },
    )
    body = response.json()
    assert body["success"] is True
    assert "BEGIN_RETRIEVED_CONTENT" in body["sanitized_payload"]
