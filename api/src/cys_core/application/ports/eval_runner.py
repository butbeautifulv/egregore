from __future__ import annotations

from typing import Protocol

from cys_core.domain.eval.models import EvalDataset, EvalRun, EvalSampleResult


class EvalRunnerPort(Protocol):
    def run(self, dataset: EvalDataset, *, run: EvalRun) -> EvalRun: ...


class EvalBackendPort(Protocol):
    def persist_run(self, run: EvalRun) -> None: ...

    def persist_artifacts(self, run_id: str, results: list[EvalSampleResult]) -> None: ...
