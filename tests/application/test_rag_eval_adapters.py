from __future__ import annotations

from cys_core.application.evals.rag_adapters import FaithEvalAdapter, FActScoreAdapter, RagasAdapter
from cys_core.domain.rag.eval_export import RagEvalTriple


def test_adapters_exist_and_return_stub_status() -> None:
    triple = RagEvalTriple(question="q", answer="a", contexts=["c"], context_ids=["id"])
    assert RagasAdapter().score_faithfulness(triple)["status"] == "not_installed"
    assert FaithEvalAdapter().score_unanswerable(triple)["status"] == "not_installed"
    assert FActScoreAdapter().score(answer="a")["status"] == "not_installed"

