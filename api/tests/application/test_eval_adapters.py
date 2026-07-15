from __future__ import annotations

from cys_core.application.eval.adapters import RagasAdapterSkeleton
from cys_core.application.routing.quality_router import ScoreQualityRouter
from cys_core.domain.memory.records import MemoryRecord, RetrievalContext
from cys_core.domain.quality.models import PersonaQuality


def test_memory_record_roundtrip() -> None:
    rec = MemoryRecord(content="x", persona="consultant", tenant_id="t1")
    assert rec.id.startswith("mrec-")


def test_retrieval_context_provenance() -> None:
    ctx = RetrievalContext(query="q", chunk_ids=["c1"], source_spans=["s1"])
    assert ctx.chunk_ids == ["c1"]


def test_ragas_skeleton() -> None:
    rag = RagasAdapterSkeleton()
    assert rag.faithfulness("a", ["c"]) == 1.0


def test_quality_router_orders_by_score() -> None:
    router = ScoreQualityRouter()
    q1 = PersonaQuality(persona="a")
    q1.merge_metric("pass", 0.2)
    q2 = PersonaQuality(persona="b")
    q2.merge_metric("pass", 0.9)
    ranked = router.rank_personas(["a", "b"], qualities=[q1, q2])
    assert ranked[0] == "b"
