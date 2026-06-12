# Contributing

## Before opening a PR

1. Run `./scripts/ruff_fix.sh` (organize imports, lint, format).
2. Run `uv run lint-imports` — import boundaries must stay green.
3. Run tests (low memory — one pytest process per `tests/<dir>/`):
   ```bash
   ./scripts/pytest_batches.sh
   ```
   With coverage + domain gate:
   ```bash
   ./scripts/pytest_batches.sh --cov --domain-gate
   ```
4. Domain only (fast):
   ```bash
   USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/domain/ -q \
     --cov=cys_core/domain --cov-fail-under=100
   ```
5. Layered coverage report: `./scripts/coverage_report.sh`

## Architecture rules

- `cys_core/domain` — no imports from infrastructure, bootstrap, or `interfaces/`.
- `cys_core/application` — depends on domain ports only; use cases live under `application/use_cases/`.
- Delivery code lives in `interfaces/` only.
- Wire dependencies in `bootstrap/container.py`, not inside domain or use-case modules.

## Coverage targets

| Layer | Target |
|-------|--------|
| `cys_core/domain` | 100% (CI fail) |
| `cys_core/application` | ≥90% (report in CI; fail gate when green) |
| `cys_core/infrastructure` | ≥95% (report in CI; fail gate when green) |

## Security / adversarial

Changes touching ingress sanitization, tool gateway, RAG ingest, or HITL flows should run:

```bash
USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/adversarial/ -q
```
