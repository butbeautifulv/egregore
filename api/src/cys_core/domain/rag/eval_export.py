from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.rag.models import RetrievalResult


class RagEvalTriple(BaseModel):
    """Eval-native export shape for RAGAS/FaithEval-style adapters."""

    question: str
    answer: str
    contexts: list[str] = Field(default_factory=list)
    context_ids: list[str] = Field(default_factory=list)
    provenance: list[dict[str, Any]] = Field(default_factory=list)
    denied_count: int = 0


def export_rag_triple(*, question: str, answer: str, retrieval: RetrievalResult) -> RagEvalTriple:
    contexts = [c.text for c in retrieval.chunks]
    context_ids = [c.chunk_id for c in retrieval.chunks]
    provenance = [
        {
            "chunk_id": c.chunk_id,
            "source_id": c.provenance.source_id,
            "source_name": c.provenance.source_name,
            "content_hash": c.provenance.content_hash,
        }
        for c in retrieval.chunks
    ]
    return RagEvalTriple(
        question=question,
        answer=answer,
        contexts=contexts,
        context_ids=context_ids,
        provenance=provenance,
        denied_count=retrieval.denied_count,
    )

