from __future__ import annotations

import pytest

from cys_core.application.follow_up.intent import classify_follow_up_mode, classify_operator_intent


@pytest.mark.unit
def test_classify_operator_intent_initial_qa() -> None:
    assert classify_operator_intent("help me triage", mode="qa", context="initial") == "initial_qa"


@pytest.mark.unit
def test_classify_operator_intent_initial_orchestrate_coerces_to_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.application.follow_up.intent.get_settings",
        lambda: type("S", (), {"follow_up_plan_enabled": True})(),
    )
    assert (
        classify_operator_intent("re-investigate", mode="orchestrate", context="initial")
        == "follow_up_plan"
    )


@pytest.mark.unit
def test_classify_operator_intent_follow_up_delegates() -> None:
    assert (
        classify_operator_intent("explain timeline", mode="qa", context="follow_up", prior_operator_turns=2)
        == "follow_up_qa"
    )


@pytest.mark.unit
def test_classify_follow_up_mode_explicit_qa() -> None:
    assert classify_follow_up_mode("anything", mode="qa", prior_operator_turns=5) == "follow_up_qa"
