from __future__ import annotations

import pytest

from cys_core.domain.rag.models import ChunkACL, DocumentProvenance, RagChunk
from cys_core.domain.security.classification import DataClassification
from interfaces.rag.retrieve import rag_query, wrap_retrieved_chunks
from interfaces.rag.store import MemoryVectorStore, QdrantVectorStore, get_vector_store, reset_vector_store


def _chunk(
    text: str,
    tenant: str = "default",
    classification: DataClassification = DataClassification.INTERNAL,
) -> RagChunk:
    return RagChunk(
        chunk_id=f"id-{hash(text)}",
        text=text,
        acl=ChunkACL(tenant=tenant, classification=classification, roles=["analyst"]),
        provenance=DocumentProvenance(source_id="doc", content_hash="hash"),
    )


@pytest.fixture(autouse=True)
def _reset_store():
    reset_vector_store()
    yield
    reset_vector_store()


@pytest.mark.unit
def test_memory_vector_store_search():
    store = MemoryVectorStore()
    store.upsert([_chunk("DNS beaconing investigation steps")])
    hits = store.search("beaconing DNS")
    assert len(hits) == 1


@pytest.mark.unit
def test_rag_query_acl_blocks_cross_tenant():
    store = MemoryVectorStore()
    store.upsert([_chunk("tenant secret playbook", tenant="tenant-a")])
    result = rag_query("secret playbook", persona="soc", tenant="tenant-b", store=store)
    assert result.fail_closed is True
    assert result.error


@pytest.mark.unit
def test_rag_query_returns_wrapped_chunks():
    store = MemoryVectorStore()
    store.upsert([_chunk("powershell encoded command triage")])
    result = rag_query("powershell triage", persona="soc", tenant="default", store=store)
    assert not result.fail_closed
    wrapped = wrap_retrieved_chunks(result.chunks)
    assert "BEGIN_RETRIEVED_CONTENT" in wrapped
    assert "END_RETRIEVED_CONTENT" in wrapped


@pytest.mark.unit
def test_rag_query_empty_query_fail_closed():
    result = rag_query("   ", persona="soc")
    assert result.fail_closed is True


@pytest.mark.unit
def test_qdrant_store_falls_back_without_broker(monkeypatch):
    def _init_without_client(self, *a, **k):
        self._client = None
        self._fallback = MemoryVectorStore()

    monkeypatch.setattr("interfaces.rag.store.QdrantVectorStore.__init__", _init_without_client)
    store = QdrantVectorStore(url="http://invalid:6333")
    store.upsert([_chunk("fallback chunk")])
    assert store.search("fallback")


@pytest.mark.unit
def test_get_vector_store_uses_memory_by_default():
    store = get_vector_store()
    assert isinstance(store, MemoryVectorStore)
