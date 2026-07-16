from __future__ import annotations

from cys_core.domain.rag.eval_export import export_rag_triple
from cys_core.domain.rag.models import ChunkACL, DocumentProvenance, RagChunk, RetrievalResult


def test_export_rag_triple_includes_context_ids_and_provenance() -> None:
    retrieval = RetrievalResult(
        query="q",
        chunks=[
            RagChunk(
                chunk_id="c1",
                text="ctx1",
                provenance=DocumentProvenance(source_id="s1", source_name="doc", content_hash="h"),
                acl=ChunkACL(),
            )
        ],
        denied_count=2,
    )
    triple = export_rag_triple(question="q", answer="a", retrieval=retrieval)
    assert triple.context_ids == ["c1"]
    assert triple.contexts == ["ctx1"]
    assert triple.denied_count == 2
    assert triple.provenance[0]["source_id"] == "s1"

