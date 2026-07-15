from __future__ import annotations

from cys_core.benchmarks.gaia_normalizer import normalize_gaia_answer, score_gaia


def test_normalize_number():
    assert normalize_gaia_answer("The answer is 42 units.", answer_type="number") == "42"


def test_score_gaia_string():
    assert score_gaia("Paris", "paris", answer_type="string") is True


def test_boxed_answer():
    assert normalize_gaia_answer(r"Final: \boxed{2020}") == "2020"
