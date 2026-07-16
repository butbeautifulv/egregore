from __future__ import annotations

from cys_core.domain.memory.records import MemoryRecord, RetrievalContext


def test_memory_record_roundtrip() -> None:
    rec = MemoryRecord(content="x", persona="consultant", tenant_id="t1")
    assert rec.id.startswith("mrec-")


def test_retrieval_context_provenance() -> None:
    ctx = RetrievalContext(query="q", chunk_ids=["c1"], source_spans=["s1"])
    assert ctx.chunk_ids == ["c1"]
