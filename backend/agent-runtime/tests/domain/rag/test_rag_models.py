from __future__ import annotations

import pytest

from cys_core.domain.rag.models import ChunkACL, DocumentProvenance, RagChunk, RetrievalResult
from cys_core.domain.security.classification import DataClassification


@pytest.mark.unit
def test_rag_chunk_defaults():
    provenance = DocumentProvenance(source_id="doc-1", content_hash="abc")
    chunk = RagChunk(chunk_id="c1", text="beaconing playbook", provenance=provenance)
    assert chunk.acl.classification == DataClassification.INTERNAL
    assert chunk.token_estimate == 0


@pytest.mark.unit
def test_retrieval_result_fail_closed():
    result = RetrievalResult(query="test", fail_closed=True, error="blocked")
    assert result.chunks == []
    assert result.error == "blocked"


@pytest.mark.unit
def test_chunk_acl_tenant():
    acl = ChunkACL(tenant="acme", roles=["analyst", "soc"])
    assert acl.tenant == "acme"
    assert "soc" in acl.roles
