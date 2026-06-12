from __future__ import annotations

from typing import Protocol

from rapidfuzz import fuzz

from bootstrap.settings import settings
from cys_core.domain.rag.models import RagChunk


class VectorStore(Protocol):
    def upsert(self, chunks: list[RagChunk]) -> int: ...

    def search(self, query: str, *, limit: int = 5) -> list[RagChunk]: ...

    def delete_tenant(self, tenant: str) -> int: ...


class MemoryVectorStore:
    """In-memory vector store with fuzzy text match (dev/test fallback)."""

    def __init__(self) -> None:
        self._chunks: list[RagChunk] = []

    def upsert(self, chunks: list[RagChunk]) -> int:
        self._chunks.extend(chunks)
        return len(chunks)

    def search(self, query: str, *, limit: int = 5) -> list[RagChunk]:
        scored = [(fuzz.partial_ratio(query.lower(), chunk.text.lower()), chunk) for chunk in self._chunks]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in scored[:limit] if score > 0]

    def delete_tenant(self, tenant: str) -> int:
        before = len(self._chunks)
        self._chunks = [c for c in self._chunks if c.acl.tenant != tenant]
        return before - len(self._chunks)

    def clear(self) -> None:
        self._chunks.clear()


class QdrantVectorStore:
    """Qdrant-backed store with memory fallback when client unavailable."""

    def __init__(self, url: str | None = None, collection: str = "cys_rag") -> None:
        self.url = url or settings.qdrant_url
        self.collection = collection
        self._fallback = MemoryVectorStore()
        self._client = None
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import Distance, PointStruct, VectorParams

            self._client = QdrantClient(url=self.url)
            self._PointStruct = PointStruct
            if not self._client.collection_exists(self.collection):
                self._client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=8, distance=Distance.COSINE),
                )
        except Exception:
            self._client = None

    def _vector(self, text: str) -> list[float]:
        digest = sum(ord(c) for c in text[:64]) or 1
        return [((digest >> (i * 4)) % 100) / 100.0 for i in range(8)]

    def upsert(self, chunks: list[RagChunk]) -> int:
        if self._client is None:
            return self._fallback.upsert(chunks)
        points = [
            self._PointStruct(
                id=chunk.chunk_id,
                vector=self._vector(chunk.text),
                payload=chunk.model_dump(),
            )
            for chunk in chunks
        ]
        self._client.upsert(collection_name=self.collection, points=points)
        return len(points)

    def search(self, query: str, *, limit: int = 5) -> list[RagChunk]:
        if self._client is None:
            return self._fallback.search(query, limit=limit)

        hits = self._client.search(
            collection_name=self.collection,
            query_vector=self._vector(query),
            limit=limit,
        )
        return [RagChunk.model_validate(hit.payload) for hit in hits]

    def delete_tenant(self, tenant: str) -> int:
        if self._client is None:
            return self._fallback.delete_tenant(tenant)
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue

        self._client.delete(
            collection_name=self.collection,
            points_selector=Filter(must=[FieldCondition(key="acl.tenant", match=MatchValue(value=tenant))]),
        )
        return 0


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is not None:
        return _store
    if settings.use_qdrant:
        _store = QdrantVectorStore()
    else:
        _store = MemoryVectorStore()
    return _store


def reset_vector_store() -> None:
    global _store
    _store = None
