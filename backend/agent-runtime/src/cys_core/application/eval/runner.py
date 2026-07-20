from __future__ import annotations

from cys_core.application.ports.eval_runner import EvalRunnerPort
from cys_core.domain.eval.models import EvalDataset, EvalMetric, EvalRun, EvalSampleResult


class DryRunEvalRunner:
  """Minimal runner for local eval plane smoke."""

  def run(self, dataset: EvalDataset, *, run: EvalRun) -> EvalRun:
    run.start()
    for case in dataset.cases:
      run.results.append(
        EvalSampleResult(
          case_id=case.id,
          metrics=[EvalMetric(name="smoke_pass", value=1.0, passed=True)],
        )
      )
    run.finish_ok()
    return run


def build_runner(*, dry_run: bool = True) -> EvalRunnerPort:
  return DryRunEvalRunner()
