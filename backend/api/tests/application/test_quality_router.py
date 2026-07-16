from __future__ import annotations

from cys_core.application.routing.quality_router import ScoreQualityRouter
from cys_core.domain.quality.models import PersonaQuality


def test_quality_router_orders_by_score() -> None:
    router = ScoreQualityRouter()
    q1 = PersonaQuality(persona="a")
    q1.merge_metric("pass", 0.2)
    q2 = PersonaQuality(persona="b")
    q2.merge_metric("pass", 0.9)
    ranked = router.rank_personas(["a", "b"], qualities=[q1, q2])
    assert ranked[0] == "b"
