from __future__ import annotations

from typing import Protocol

from cys_core.domain.quality.models import PersonaQuality


class QualityAwareRouterPort(Protocol):
    def rank_personas(self, candidates: list[str], *, qualities: list[PersonaQuality]) -> list[str]: ...


class ScoreQualityRouter:
    """Route personas by mean eval signal (higher first)."""

    def rank_personas(self, candidates: list[str], *, qualities: list[PersonaQuality]) -> list[str]:
        scores: dict[str, float] = {}
        for q in qualities:
            if not q.signals:
                scores[q.persona] = 0.0
                continue
            scores[q.persona] = sum(s.value for s in q.signals) / len(q.signals)
        return sorted(candidates, key=lambda p: scores.get(p, 0.0), reverse=True)
