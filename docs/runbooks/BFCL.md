# BFCL-lite eval runbook

Local skeleton adapter: `cys_core.application.eval.adapters.BfclAdapterSkeleton`.

## Smoke

```bash
cd projects/egregore
uv run python -c "from cys_core.application.eval.adapters import BfclAdapterSkeleton; print(BfclAdapterSkeleton().simple_case('x'))"
uv run python scripts/evals/sgr_bfcl_ab.py --help
```

## Suites (planned)

| Suite | Adapter method | Notes |
|-------|----------------|-------|
| simple | `simple_case` | single tool selection |
| multiple | `multiple_tools` | parallel tool calls |
| multiturn | `multiturn` | state carry-over |
| irrelevance | `irrelevance` | reject spurious tools |

## Artifacts

- Fixture: `tests/fixtures/eval_ci_small.json`
- Trajectory metrics: `BfclAdapterSkeleton.trajectory_score`

## Grafana

Dashboard **Egregore — Eval & Quality** (`/d/egregore-eval`) — RAG + policy fallback rates.
