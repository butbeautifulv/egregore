from __future__ import annotations

import pytest

from cys_core.domain.rag.models import ChunkACL, DocumentProvenance, RagChunk
from interfaces.rag.retrieve import rag_query
from interfaces.rag.store import MemoryVectorStore


@pytest.mark.integration
def test_rag_cross_tenant_fail_closed():
    store = MemoryVectorStore()
    store.upsert(
        [
            RagChunk(
                chunk_id="c1",
                text="tenant secret data",
                acl=ChunkACL(tenant="acme", roles=["analyst"]),
                provenance=DocumentProvenance(source_id="kb", content_hash="h"),
            )
        ]
    )
    result = rag_query("secret", persona="soc", tenant="other", store=store)
    assert result.fail_closed is True
    assert not result.chunks
