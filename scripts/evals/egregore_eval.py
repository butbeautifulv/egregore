from __future__ import annotations

import argparse
import json

from cys_core.domain.eval.models import EvalCase, EvalDataset, EvalRun


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--suite", default="dry-run")
    p.add_argument("--profile", default="")
    p.add_argument("--persona", default="")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--model", default="")
    p.add_argument("--mode", default="")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    dataset = EvalDataset(
        id="tiny",
        name="tiny",
        cases=[EvalCase(id=f"case-{i}", input={"q": f"q{i}"}) for i in range(max(0, args.limit))],
    )
    run = EvalRun(run_id="dry", dataset_id=dataset.id, suite_id=args.suite, profile_id=args.profile, persona=args.persona)
    if args.dry_run:
        print(json.dumps({"run": run.model_dump(mode="json"), "dataset_cases": len(dataset.cases)}, ensure_ascii=False))
        return 0
    print(json.dumps({"error": "no runners configured (use --dry-run)"}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

