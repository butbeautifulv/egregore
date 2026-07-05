from __future__ import annotations

import argparse
import json
import uuid

from cys_core.application.eval.runner import build_runner
from cys_core.domain.eval.models import EvalCase, EvalDataset, EvalRun


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Egregore eval CLI")
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
    run = EvalRun(
        run_id=f"run-{uuid.uuid4().hex[:8]}",
        dataset_id=dataset.id,
        suite_id=args.suite,
        profile_id=args.profile,
        persona=args.persona,
        model=args.model,
    )
    if args.dry_run or args.suite == "dry-run":
        runner = build_runner(dry_run=True)
        finished = runner.run(dataset, run=run)
        print(json.dumps(finished.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({"error": "suite not configured", "suite": args.suite}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
