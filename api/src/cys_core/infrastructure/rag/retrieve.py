from __future__ import annotations

from bootstrap.settings import settings
from cys_core.domain.rag.models import ChunkACL, RagChunk, RetrievalResult
from cys_core.domain.security.classification import SecureContextBuilder
from cys_core.domain.security.content_delimiters import wrap_retrieved_chunks_body
from cys_core.observability.metrics import metrics
from cys_core.infrastructure.rag.store import VectorStore, get_vector_store


def _acl_allows(chunk_acl: ChunkACL, ctx: SecureContextBuilder, persona_roles: list[str]) -> bool:
    if chunk_acl.tenant != ctx.tenant and ctx.tenant != "default":
        return False
    if not ctx.can_access(chunk_acl.classification):
        return False
    if chunk_acl.roles and persona_roles:
        return bool(set(chunk_acl.roles) & set(persona_roles))
    return True


def wrap_retrieved_chunks(chunks: list[RagChunk]) -> str:
    body = "\n\n---\n\n".join(chunk.text for chunk in chunks)
    return wrap_retrieved_chunks_body(body)


def rag_query(
    query: str,
    *,
    persona: str,
    tenant: str = "default",
    roles: list[str] | None = None,
    store: VectorStore | None = None,
    max_chunks: int | None = None,
) -> RetrievalResult:
    """ACL pre-filtered retrieval. Fail-closed on store errors."""
    if not query.strip():
        metrics.record_rag_retrieval(tenant, denied=True)
        return RetrievalResult(query=query, fail_closed=True, error="empty query")
    limit = max_chunks or settings.rag_max_chunks
    ctx = SecureContextBuilder(persona=persona, tenant=tenant, roles=roles or ["analyst"])
    persona_roles = roles or ["analyst"]
    try:
        vector_store = store or get_vector_store()
        candidates = vector_store.search(query, limit=limit * 3)
    except Exception as exc:
        metrics.record_rag_retrieval(tenant, denied=True)
        return RetrievalResult(query=query, fail_closed=True, error=f"retrieval failed: {exc}")

    allowed: list[RagChunk] = []
    denied = 0
    for chunk in candidates:
        if _acl_allows(chunk.acl, ctx, persona_roles):
            if ctx.include_in_context(chunk.acl.classification):
                allowed.append(chunk)
        else:
            denied += 1
        if len(allowed) >= limit:
            break

    if not allowed:
        metrics.record_rag_retrieval(tenant, denied=True)
        return RetrievalResult(
            query=query,
            chunks=[],
            denied_count=denied,
            fail_closed=True,
            error="no ACL-authorized chunks retrieved",
        )

    metrics.record_rag_retrieval(tenant, denied=denied > 0)
    return RetrievalResult(query=query, chunks=allowed, denied_count=denied)
