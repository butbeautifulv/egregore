# Eval plane migration guide

Move from ad-hoc scripts to the unified eval CLI and catalog quality hooks.

## Before

- One-off pytest modules per benchmark
- Manual Langfuse UI inspection

## After

| Component | Path |
|-----------|------|
| Models | `cys_core/domain/eval/models.py` |
| Runner port | `cys_core/application/ports/eval_runner.py` |
| Dry-run runner | `cys_core/application/eval/runner.py` |
| Adapters | `cys_core/application/eval/adapters.py` |
| CLI | `scripts/evals/egregore_eval.py` |
| Artifacts | `cys_core/infrastructure/eval/artifact_store.py` |

## Commands

```bash
cd projects/egregore
uv run python scripts/evals/egregore_eval.py --suite tiny --limit 3 --dry-run
uv run pytest tests/application/test_eval_adapters.py -q
```

## Quality routing

Persona scores feed `ScoreQualityRouter` (`cys_core/application/routing/quality_router.py`) and catalog `/catalog/evaluations`.

## Grafana

Import dashboard `deploy/observability/grafana/dashboards/egregore/egregore-eval.json` (uid `egregore-eval`).
