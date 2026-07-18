from __future__ import annotations

from typing import Any, Protocol

import structlog
from rapidfuzz import fuzz

from bootstrap.settings import settings
from cys_core.domain.rag.models import RagChunk

logger = structlog.get_logger(__name__)


class QdrantUnavailableError(Exception):
    """Raised instead of silently degrading — rag_query() (cys_core.infrastructure.rag.retrieve)
    already has fail-closed handling designed for exactly this (RetrievalResult.fail_closed),
    docs/MICROSERVICES_SPLIT_PLAN.md §10.5's requirement — but QdrantVectorStore previously
    swallowed the failure and returned empty/stale results from an in-memory store instead of
    raising, silently bypassing that handling. See §39."""


class VectorStore(Protocol):
    def upsert(self, chunks: list[RagChunk]) -> int: ...

    def search(self, query: str, *, limit: int = 5, tenant: str | None = None) -> list[RagChunk]: ...

    def delete_tenant(self, tenant: str) -> int: ...


class MemoryVectorStore:
    """In-memory vector store with fuzzy text match (dev/test fallback)."""

    def __init__(self) -> None:
        self._chunks: list[RagChunk] = []

    def upsert(self, chunks: list[RagChunk]) -> int:
        self._chunks.extend(chunks)
        return len(chunks)

    def search(self, query: str, *, limit: int = 5, tenant: str | None = None) -> list[RagChunk]:
        candidates = self._chunks
        # §10.5/§43: pre-filter by tenant before scoring, not just after — "default" keeps
        # today's deliberate cross-tenant-visible semantic (SecureContextBuilder/_acl_allows
        # in retrieve.py), everything else is scoped as early as possible.
        if tenant is not None and tenant != "default":
            candidates = [c for c in candidates if c.acl.tenant == tenant]
        scored = [(fuzz.partial_ratio(query.lower(), chunk.text.lower()), chunk) for chunk in candidates]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in scored[:limit] if score > 0]

    def delete_tenant(self, tenant: str) -> int:
        before = len(self._chunks)
        self._chunks = [c for c in self._chunks if c.acl.tenant != tenant]
        return before - len(self._chunks)

    def clear(self) -> None:
        self._chunks.clear()


class QdrantVectorStore:
    """Qdrant-backed store. Raises QdrantUnavailableError rather than silently degrading —
    RAG retrieval security requires failing closed (§10.5/§39), not quietly answering from an
    empty in-memory store that was never populated with the same data."""

    def __init__(self, url: str | None = None, collection: str = "cys_rag") -> None:
        self.url = url or settings.qdrant_url
        self.collection = collection
        self._client: Any = None
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
        except Exception as exc:
            self._client = None
            logger.warning("qdrant_connect_failed", url=self.url, error=str(exc))

    def _vector(self, text: str) -> list[float]:
        if settings.use_real_embeddings:
            return self._embedding_vector(text)
        digest = sum(ord(c) for c in text[:64]) or 1
        return [((digest >> (i * 4)) % 100) / 100.0 for i in range(8)]

    def _embedding_vector(self, text: str) -> list[float]:
        try:
            # litellm isn't part of this package (no agent-execution
            # frameworks, see docs/MICROSERVICES_SPLIT_PLAN.md §21.5) — with
            # settings.use_real_embeddings on, this always falls through to
            # the pseudo-embedding fallback below. Deliberate, not stale —
            # same pattern as multimodal.py's vision_analyze.
            from litellm import embedding  # ty: ignore[unresolved-import]

            response = embedding(model=settings.llm_model, input=[text])
            vector = response.data[0]["embedding"]
            return [float(value) for value in vector]
        except Exception:
            digest = sum(ord(c) for c in text[:64]) or 1
            return [((digest >> (i * 4)) % 100) / 100.0 for i in range(8)]

    def upsert(self, chunks: list[RagChunk]) -> int:
        if self._client is None:
            raise QdrantUnavailableError("Qdrant client unavailable — refusing to silently drop an upsert")
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

    def search(self, query: str, *, limit: int = 5, tenant: str | None = None) -> list[RagChunk]:
        if self._client is None:
            raise QdrantUnavailableError("Qdrant client unavailable — refusing to silently degrade retrieval")

        query_filter = None
        if tenant is not None and tenant != "default":
            # §10.5/§43: filter by tenant at query time (same Filter/FieldCondition shape
            # delete_tenant() already uses below) instead of fetching top-K across every
            # tenant and relying only on the Python-side ACL check in retrieve.py's
            # rag_query() afterward — RAG_Security_Cheat_Sheet.md §4/§6 warns that
            # post-retrieval filtering is weaker than pre-retrieval. "default" keeps its
            # existing deliberate cross-tenant-visible semantic (see MemoryVectorStore.search
            # and _acl_allows in retrieve.py) — unfiltered here too, for the same reason.
            from qdrant_client.http.models import FieldCondition, Filter, MatchValue

            query_filter = Filter(must=[FieldCondition(key="acl.tenant", match=MatchValue(value=tenant))])

        hits = getattr(self._client, "search")(
            collection_name=self.collection,
            query_vector=self._vector(query),
            limit=limit,
            query_filter=query_filter,
        )
        return [RagChunk.model_validate(hit.payload) for hit in hits]

    def delete_tenant(self, tenant: str) -> int:
        if self._client is None:
            raise QdrantUnavailableError("Qdrant client unavailable — refusing to silently no-op a delete")
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
