from __future__ import annotations

from typing import Protocol

from cys_core.domain.eval.models import EvalDataset, EvalRun


class EvalRunnerPort(Protocol):
    def run(self, *, dataset: EvalDataset, suite_id: str, profile_id: str = "", persona: str = "") -> EvalRun: ...

