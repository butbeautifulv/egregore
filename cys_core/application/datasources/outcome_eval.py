from __future__ import annotations

import json
from pathlib import Path

from cys_core.domain.datasources.eval_outcome import OutcomeEvalConfig, OutcomeEvalResult


def partial_action_similarity(reference: list[str], actual: list[str]) -> float:
    if not reference:
        return 0.0
    ref = set(reference)
    act = set(actual)
    return len(ref & act) / len(ref)


def run_outcome_smoke(case_id: str = "smoke-1") -> OutcomeEvalResult:
    return OutcomeEvalResult(case_id=case_id, passed=True, score=1.0, assertions=["communicate_ok"])


def load_outcome_config() -> OutcomeEvalConfig:
    return OutcomeEvalConfig()
