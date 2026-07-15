from __future__ import annotations

from typing import Any

from cys_core.infrastructure.rag.retrieve import rag_query, wrap_retrieved_chunks


def rag_query_tool(
    *,
    query: str,
    persona: str = "soc",
    tenant: str = "default",
    roles: list[str] | None = None,
) -> dict[str, Any]:
    """Read-only RAG retrieval with ACL pre-filter and fail-closed semantics."""
    result = rag_query(query, persona=persona, tenant=tenant, roles=roles)
    if result.fail_closed or result.error:
        return {
            "success": False,
            "fail_closed": True,
            "error": result.error or "retrieval blocked",
            "denied_count": result.denied_count,
            "query": query,
        }

    wrapped = wrap_retrieved_chunks(result.chunks)
    return {
        "success": True,
        "fail_closed": False,
        "query": query,
        "chunk_count": len(result.chunks),
        "denied_count": result.denied_count,
        "content": wrapped,
        "sources": [
            {
                "chunk_id": c.chunk_id,
                "source_id": c.provenance.source_id,
                "hash": c.provenance.content_hash,
                "tenant": c.acl.tenant,
                "classification": c.acl.classification.value,
            }
            for c in result.chunks
        ],
    }
