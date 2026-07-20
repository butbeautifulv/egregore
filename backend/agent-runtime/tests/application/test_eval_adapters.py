from __future__ import annotations

from cys_core.application.eval.adapters import RagasAdapterSkeleton


def test_ragas_skeleton() -> None:
    rag = RagasAdapterSkeleton()
    assert rag.faithfulness("a", ["c"]) == 1.0
