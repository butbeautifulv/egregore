from __future__ import annotations

import pytest

from cys_core.domain.rag.models import ChunkACL, DocumentProvenance, RagChunk
from cys_core.domain.security.classification import DataClassification
from cys_core.infrastructure.rag.store import QdrantUnavailableError
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
def test_qdrant_store_raises_without_broker_instead_of_silently_degrading(monkeypatch):
    """§10.5/§39: RAG retrieval must fail closed when Qdrant is unreachable, not silently
    answer from an empty in-memory store the caller never populated. QdrantVectorStore used
    to swallow this and return real-looking (but wrong/empty) results; it must now raise so
    rag_query()'s existing fail-closed handling actually triggers."""

    def _init_without_client(self, *a, **k):
        self._client = None

    monkeypatch.setattr("interfaces.rag.store.QdrantVectorStore.__init__", _init_without_client)
    store = QdrantVectorStore(url="http://invalid:6333")
    with pytest.raises(QdrantUnavailableError):
        store.upsert([_chunk("should not silently vanish")])
    with pytest.raises(QdrantUnavailableError):
        store.search("anything")
    with pytest.raises(QdrantUnavailableError):
        store.delete_tenant("tenant-a")


@pytest.mark.unit
def test_rag_query_fails_closed_when_qdrant_unavailable(monkeypatch):
    """End-to-end proof, not just a unit-level raise: rag_query()'s existing try/except
    around vector_store.search() actually catches QdrantUnavailableError and reports
    fail_closed=True — the fix closes the gap at the use case boundary the agent sees,
    not just inside the store class."""

    def _init_without_client(self, *a, **k):
        self._client = None

    monkeypatch.setattr("interfaces.rag.store.QdrantVectorStore.__init__", _init_without_client)
    store = QdrantVectorStore(url="http://invalid:6333")
    result = rag_query("anything", persona="soc", tenant="default", store=store)
    assert result.fail_closed is True
    assert result.error and "unavailable" in result.error.lower()


@pytest.mark.unit
def test_get_vector_store_uses_memory_by_default():
    store = get_vector_store()
    assert isinstance(store, MemoryVectorStore)
