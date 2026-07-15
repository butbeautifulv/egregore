from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cys_core.domain.rag.eval_export import RagEvalTriple


@dataclass(frozen=True)
class OptionalEvalDependencyError(RuntimeError):
    package: str


class RagasAdapter:
    """Lazy adapter shell; real scoring is optional dependency."""

    def score_faithfulness(self, triple: RagEvalTriple) -> dict[str, Any]:
        _ = triple
        return {"metric": "ragas_faithfulness", "status": "not_installed"}


class FaithEvalAdapter:
    def score_unanswerable(self, triple: RagEvalTriple) -> dict[str, Any]:
        _ = triple
        return {"metric": "faitheval_unanswerable", "status": "not_installed"}


class FActScoreAdapter:
    def score(self, *, answer: str, knowledge_base: str = "wikipedia") -> dict[str, Any]:
        _ = (answer, knowledge_base)
        return {"metric": "factscore", "status": "not_installed"}

