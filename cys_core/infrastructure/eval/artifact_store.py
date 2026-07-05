from __future__ import annotations

import json
from pathlib import Path

from cys_core.domain.eval.models import EvalArtifact, EvalRun, EvalSampleResult


class FilesystemEvalArtifactStore:
    def __init__(self, root: str | Path = "/tmp/egregore-eval-artifacts") -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def write(self, run_id: str, results: list[EvalSampleResult]) -> list[EvalArtifact]:
        out: list[EvalArtifact] = []
        run_dir = self._root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        for sample in results:
            path = run_dir / f"{sample.case_id}.json"
            path.write_text(json.dumps(sample.model_dump(mode="json"), indent=2), encoding="utf-8")
            out.append(
                EvalArtifact(
                    name=sample.case_id,
                    uri=str(path),
                    mime_type="application/json",
                )
            )
        return out
