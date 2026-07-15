from __future__ import annotations

from cys_core.application.datasources.outcome_eval import partial_action_similarity, run_outcome_smoke
from cys_core.domain.datasources.governance import DataSourceGovernance, WriteGateRequest


def test_partial_similarity_diagnostic() -> None:
    assert partial_action_similarity(["a", "b"], ["a"]) == 0.5


def test_write_gate_requires_actor() -> None:
    gov = DataSourceGovernance()
    assert gov.write_gate_required
    req = WriteGateRequest(actor="", reason="test")
    assert not req.actor


def test_outcome_smoke() -> None:
    assert run_outcome_smoke().passed
