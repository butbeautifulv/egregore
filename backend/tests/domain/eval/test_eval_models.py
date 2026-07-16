from __future__ import annotations

from cys_core.domain.eval.models import EvalCase, EvalDataset, EvalRun


def test_eval_models_roundtrip() -> None:
    ds = EvalDataset(id="d1", cases=[EvalCase(id="c1", input={"x": 1})])
    run = EvalRun(run_id="r1", dataset_id=ds.id, suite_id="s1")
    dumped = run.model_dump(mode="json")
    loaded = EvalRun.model_validate(dumped)
    assert loaded.dataset_id == "d1"

