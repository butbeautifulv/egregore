from __future__ import annotations

import pytest

from cys_core.benchmarks.gaia_pipeline import detect_gaia_answer_type, extract_gaia_final_answer
from cys_core.benchmarks.gaia_normalizer import normalize_gaia_answer


@pytest.mark.unit
def test_detect_gaia_answer_type_heuristic():
    assert detect_gaia_answer_type("How many countries?") == "number"


@pytest.mark.unit
def test_extract_gaia_final_answer_heuristic():
    out = extract_gaia_final_answer(
        question="Capital of France?",
        summary="Paris",
        answer_type="string",
    )
    assert out["normalized_answer"] == "paris"


@pytest.mark.unit
def test_gaia_normalizer_number():
    assert normalize_gaia_answer("42 units", answer_type="number") == "42"
