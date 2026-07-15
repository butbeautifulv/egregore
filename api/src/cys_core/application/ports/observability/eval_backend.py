from __future__ import annotations

from typing import Any, Protocol

from cys_core.domain.observability.models import EvalScore


class EvalBackendPort(Protocol):
    def run_experiment(self, dataset: str, *, evaluator: str = "default") -> list[EvalScore]: ...

    def record_score(self, trace_id: str, name: str, value: float, *, comment: str = "") -> None: ...
