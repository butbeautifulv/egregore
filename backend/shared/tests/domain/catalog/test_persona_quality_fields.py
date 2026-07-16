from __future__ import annotations

from cys_core.domain.catalog.models import PersonaQuality


def test_persona_quality_has_factuality_fields() -> None:
    q = PersonaQuality()
    assert hasattr(q, "factuality_score")
    assert hasattr(q, "faithfulness_score")

