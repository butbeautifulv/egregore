from __future__ import annotations

from cys_core.application.eval.runner import build_runner
from cys_core.application.guardrails.policy_gate import check_policy_fail_closed
from cys_core.domain.eval.models import EvalCase, EvalDataset, EvalRun


def test_dry_run_eval_runner() -> None:
    dataset = EvalDataset(id="tiny", name="tiny", cases=[EvalCase(id="c1", input={"q": "x"})])
    run = EvalRun(run_id="run-test", dataset_id="tiny")
    finished = build_runner(dry_run=True).run(dataset, run=run)
    assert finished.status.value == "completed"
    assert len(finished.results) == 1


def test_policy_fail_closed() -> None:
    assert not check_policy_fail_closed(policy_loaded=False, tool_name="x").allowed
    assert check_policy_fail_closed(policy_loaded=True, tool_name="search").allowed
